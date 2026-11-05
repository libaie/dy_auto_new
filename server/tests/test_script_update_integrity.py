"""Archive acceptance and the tracked packer use real ZIPs, without device I/O."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from app.services.script_service import ScriptService


def make_archive(files=None, extra=(), corrupt_hash=False):
    files = dict(files or {
        "main.js": 'require("./config"); require("./core/ai-analyzer");',
        "config.js": "module.exports = {};",
        "project.json": '{"main":"main.js"}',
        "core/ai-analyzer.js": 'module.exports = require("./decision-client");',
        "core/decision-client.js": "module.exports = 2;",
    })
    encoded = {name: value.encode() if isinstance(value, str) else value for name, value in files.items()}
    manifest = {"format": 1, "entry": "main.js", "files": {
        name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in encoded.items()
    }}
    if corrupt_hash:
        manifest["files"]["main.js"]["sha256"] = "0" * 64
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in encoded.items():
            archive.writestr(name, data)
        archive.writestr("device-update.json", json.dumps(manifest))
        for name, data in extra:
            archive.writestr(name, data)
    return output.getvalue()


@pytest.mark.parametrize("bad_package", [
    b"not a zip",
    make_archive({"main.js": 'require("./core/decision-client");', "config.js": "", "project.json": '{"main":"main.js"}'}),
    make_archive(corrupt_hash=True),
    make_archive(extra=[("../outside.js", "bad")]),
    make_archive(extra=[("/absolute.js", "bad")]),
    make_archive(extra=[("core\\alias.js", "bad")]),
    make_archive(extra=[("core/../alias.js", "bad")]),
    make_archive(extra=[("main.js", "duplicate")]),
    make_archive({"device/main.js": "", "device/config.js": "", "device/project.json": '{"main":"main.js"}'}),
], ids=["non-zip", "missing-require", "hash-mismatch", "traversal", "absolute", "backslash", "alias", "duplicate", "wrapped-root"])
def test_rejected_archive_never_replaces_download_or_advances_version(tmp_path, bad_package):
    service = ScriptService(tmp_path, tmp_path / "version.txt")
    previous = make_archive()
    service.upload_script(io.BytesIO(previous))
    old_version = service.get_version()

    with pytest.raises(ValueError):
        service.upload_script(io.BytesIO(bad_package))

    assert service.get_version() == old_version
    assert service.download_script() == previous


def test_valid_nested_local_requires_are_accepted_and_comments_are_not_dependencies(tmp_path):
    package = make_archive({
        "main.js": 'require("./config"); require("./core/nested/start"); // require("./missing-comment")\n',
        "config.js": 'module.exports = "require(\\\"./missing-string\\\")";',
        "project.json": '{"main":"main.js"}',
        "core/nested/start.js": '/* require("./missing-block") */ module.exports = require("../../data.json");',
        "data.json": '{"ready":true}',
    })
    service = ScriptService(tmp_path, tmp_path / "version.txt")
    assert service.upload_script(io.BytesIO(package)) == "0.0.1"
    assert service.download_script() == package


def test_static_require_cannot_escape_the_package_root(tmp_path):
    package = make_archive({
        "main.js": 'require("../outside");',
        "config.js": "",
        "project.json": '{"main":"main.js"}',
    })
    service = ScriptService(tmp_path, tmp_path / "version.txt")
    with pytest.raises(ValueError, match="require|outside|escape|root"):
        service.upload_script(io.BytesIO(package))
    assert service.get_version() == "0.0.0"
    assert service.download_script() is None


def test_tracked_packer_includes_new_core_modules_and_excludes_runtime_data(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "source"
    files = {
        "main.js": 'require("./config"); require("./core/decision-client");',
        "config.js": "module.exports = {};",
        "project.json": '{"main":"main.js"}',
        "core/decision-client.js": "module.exports = 1;",
        "test/no-ship.js": 'require("../not-production");',
        "spike/no-ship.js": "throw Error('spike');",
        "cache/state.json": '{"persist":true}',
        ".dy_auto_releases/old/main.js": "old release",
    }
    for name, data in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)
    output = tmp_path / "device.zip"
    completed = subprocess.run(
        [sys.executable, str(root / "tools" / "pack_device.py"), "--source", str(source), "--output", str(output)],
        capture_output=True, text=True, env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"},
    )
    assert completed.returncode == 0, completed.stderr
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {
            "main.js", "config.js", "project.json", "core/decision-client.js", "device-update.json",
        }
        manifest = json.loads(archive.read("device-update.json"))
        assert manifest["files"]["core/decision-client.js"]["sha256"] == hashlib.sha256(files["core/decision-client.js"].encode()).hexdigest()
    service = ScriptService(tmp_path / "published", tmp_path / "published" / "version.txt")
    assert service.upload_script(io.BytesIO(output.read_bytes())) == "0.0.1"


def test_tracked_packer_refuses_missing_dependency_without_overwriting_existing_output(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.js").write_text('require("./config"); require("./core/decision-client");')
    (source / "config.js").write_text("module.exports = {};")
    (source / "project.json").write_text('{"main":"main.js"}')
    output = tmp_path / "device.zip"
    output.write_bytes(b"previous package")
    completed = subprocess.run(
        [sys.executable, str(root / "tools" / "pack_device.py"), "--source", str(source), "--output", str(output)],
        capture_output=True, text=True,
    )
    assert completed.returncode != 0
    assert "decision-client" in completed.stderr
    assert output.read_bytes() == b"previous package"
