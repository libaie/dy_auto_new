#!/usr/bin/env python3
"""Build a complete, reproducible AutoJS device update ZIP using only stdlib."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from app.services.script_archive import (  # noqa: E402
    EXCLUDED_PARTS, InvalidScriptArchive, MANIFEST_NAME,
    validate_script_archive, validate_source_files,
)


def build_package(source: Path, output: Path) -> int:
    source = source.resolve()
    if not source.is_dir():
        raise InvalidScriptArchive(f"Device source directory does not exist: {source}")
    files = {}
    for filename in sorted(source.rglob("*")):
        relative = filename.relative_to(source)
        if any(part.startswith(".") or part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if filename.is_symlink():
            raise InvalidScriptArchive(f"Symlink cannot be packaged: {relative}")
        if not filename.is_file() or filename.suffix not in {".js", ".json"} or relative.as_posix() == MANIFEST_NAME:
            continue
        files[relative.as_posix()] = filename.read_bytes()
    validate_source_files(files)
    manifest = {"format": 1, "entry": "main.js", "files": {
        name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in files.items()
    }}
    contents = {**files, MANIFEST_NAME: (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(contents):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, contents[name])
    package = buffer.getvalue()
    validate_script_archive(package)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=output.name + ".", dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(package)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "device")
    parser.add_argument("--output", type=Path, default=ROOT / "device-script.zip")
    args = parser.parse_args()
    try:
        count = build_package(args.source, args.output)
    except (InvalidScriptArchive, OSError) as exc:
        print(f"Device package rejected: {exc}", file=sys.stderr)
        return 1
    print(f"Packed {count} verified runtime files: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
