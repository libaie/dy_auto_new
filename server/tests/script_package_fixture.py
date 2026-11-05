"""Small complete device archive for service and HTTP upload tests."""
import hashlib
import io
import json
import zipfile


def script_package():
    files = {
        "main.js": b'require("./config"); require("./core/decision-client");',
        "config.js": b"module.exports = {};",
        "core/decision-client.js": b"module.exports = {};",
        "project.json": b'{"main":"main.js"}',
    }
    manifest = {"format": 1, "entry": "main.js", "files": {
        name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in files.items()
    }}
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr("device-update.json", json.dumps(manifest))
    return result.getvalue()
