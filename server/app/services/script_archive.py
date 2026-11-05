"""Pure-stdlib device archive contract, shared by uploads and the local packer."""
from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import zipfile

MANIFEST_NAME = "device-update.json"
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_FILES = 1000
EXCLUDED_PARTS = {"test", "tests", "spike", "node_modules", "cache", "logs", "templates", "update"}


class InvalidScriptArchive(ValueError):
    """A package cannot be safely installed as a complete device release."""


def valid_archive_path(name: str) -> bool:
    if not isinstance(name, str) or not name or len(name) > 240:
        return False
    parts = name.split("/")
    return all(
        part and not part.startswith(".") and part not in EXCLUDED_PARTS
        and re.fullmatch(r"[A-Za-z0-9_.-]+", part)
        for part in parts
    )


def _decode_js_string(raw: str) -> str:
    def replace(match):
        if match[1]:
            return chr(int(match[1], 16))
        if match[2]:
            return chr(int(match[2], 16))
        if match[3]:
            return ""
        return {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}.get(match[4], match[4])
    return re.sub(r"\\(?:x([0-9a-fA-F]{2})|u([0-9a-fA-F]{4})|(\r?\n)|(.))", replace, raw)


def static_requires(source: str) -> list[str]:
    """Read literal require calls while skipping comments, strings and regexes.

    AutoJS sources may contain XML layouts, so a Node-only JS parser cannot be
    used here. Only lexical tokens are needed to validate local module edges.
    """
    tokens = []
    i, previous = 0, ""
    regex_before = {"", "(", "[", "{", ",", ";", ":", "=", "!", "?", "&", "|", "+", "-", "*", "%", "^", "~", "return", "throw", "case"}
    while i < len(source):
        char = source[i]
        if char.isspace():
            i += 1
            continue
        if source.startswith("//", i):
            end = source.find("\n", i + 2)
            i = len(source) if end < 0 else end + 1
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = len(source) if end < 0 else end + 2
            continue
        if char in "\"'":
            start, quote = i + 1, char
            i += 1
            while i < len(source) and source[i] != quote:
                i += 2 if source[i] == "\\" else 1
            tokens.append(("string", _decode_js_string(source[start:i])))
            previous = "string"
            i += 1
            continue
        if char == "/" and previous in regex_before:
            i += 1
            in_class = False
            while i < len(source):
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == "[":
                    in_class = True
                elif source[i] == "]":
                    in_class = False
                elif source[i] == "/" and not in_class:
                    i += 1
                    break
                i += 1
            while i < len(source) and source[i].isalpha():
                i += 1
            tokens.append(("regex", "regex"))
            previous = "regex"
            continue
        if char.isalpha() or char in "_$":
            start = i
            i += 1
            while i < len(source) and (source[i].isalnum() or source[i] in "_$"):
                i += 1
            previous = source[start:i]
            tokens.append(("name", previous))
            continue
        tokens.append(("punct", char))
        previous = char
        i += 1
    return [tokens[index + 2][1] for index, token in enumerate(tokens[:-3])
            if token == ("name", "require")
            and (index == 0 or tokens[index - 1][1] != ".")
            and tokens[index + 1][1] == "(" and tokens[index + 2][0] == "string"
            and tokens[index + 3][1] == ")"]


def _resolve_dependency(filename: str, dependency: str, filenames: set[str]) -> bool:
    parts = filename.split("/")[:-1]
    for part in dependency.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return False
            parts.pop()
        else:
            parts.append(part)
    target = "/".join(parts)
    return any(candidate in filenames for candidate in (target, target + ".js", target + ".json", target + "/index.js"))


def validate_source_files(files: dict[str, bytes]) -> None:
    for required in ("main.js", "config.js", "project.json"):
        if required not in files:
            raise InvalidScriptArchive(f"Missing root file: {required}; ZIP must contain device files directly")
    for filename in files:
        if filename == MANIFEST_NAME or not valid_archive_path(filename):
            raise InvalidScriptArchive(f"Unsafe or reserved archive path: {filename}")
    try:
        project = json.loads(files["project.json"])
    except (ValueError, UnicodeError) as exc:
        raise InvalidScriptArchive("Invalid project.json") from exc
    if not isinstance(project, dict) or project.get("main") != "main.js":
        raise InvalidScriptArchive("project.json must use main.js as its entry")
    filenames = set(files)
    for filename, content in files.items():
        if not filename.endswith(".js"):
            continue
        try:
            source = content.decode("utf-8-sig")
        except UnicodeError as exc:
            raise InvalidScriptArchive(f"JavaScript must be UTF-8: {filename}") from exc
        for dependency in static_requires(source):
            if dependency.startswith("/") or "\\" in dependency:
                raise InvalidScriptArchive(f"require outside package in {filename}: {dependency}")
            if dependency.startswith(".") and not _resolve_dependency(filename, dependency, filenames):
                raise InvalidScriptArchive(f"Missing local require in {filename}: {dependency}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidScriptArchive(f"Duplicate manifest key: {key}")
        result[key] = value
    return result


def validate_script_archive(content: bytes) -> dict:
    if not isinstance(content, bytes) or not content or len(content) > MAX_ARCHIVE_BYTES:
        raise InvalidScriptArchive("Script ZIP must be non-empty and no larger than 10 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES:
                raise InvalidScriptArchive("Too many ZIP entries")
            seen, expanded, files = set(), 0, {}
            for entry in entries:
                name = entry.filename.rstrip("/") if entry.is_dir() else entry.filename
                if not valid_archive_path(name) or name in seen:
                    raise InvalidScriptArchive(f"Unsafe or duplicate ZIP path: {entry.filename}")
                seen.add(name)
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode) or (mode & 0o170000) not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise InvalidScriptArchive(f"Non-regular ZIP entry: {entry.filename}")
                if entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise InvalidScriptArchive(f"Unsupported ZIP entry: {entry.filename}")
                expanded += entry.file_size
                if expanded > MAX_EXPANDED_BYTES:
                    raise InvalidScriptArchive("Expanded ZIP is larger than 50 MB")
                if not entry.is_dir():
                    files[name] = archive.read(entry)
            if MANIFEST_NAME not in files:
                raise InvalidScriptArchive("Missing device-update.json; build with tools/pack_device.py")
            manifest = json.loads(files.pop(MANIFEST_NAME), object_pairs_hook=_unique_object)
            if not isinstance(manifest, dict) or type(manifest.get("format")) is not int or manifest["format"] != 1 or manifest.get("entry") != "main.js":
                raise InvalidScriptArchive("Unsupported device-update.json format")
            records = manifest.get("files")
            if not isinstance(records, dict) or set(records) != set(files):
                raise InvalidScriptArchive("ZIP files do not match the update manifest")
            for name, data in files.items():
                record = records[name]
                if not isinstance(record, dict) or type(record.get("size")) is not int or record["size"] != len(data) or record.get("sha256") != hashlib.sha256(data).hexdigest():
                    raise InvalidScriptArchive(f"Size or SHA-256 mismatch: {name}")
            validate_source_files(files)
            return manifest
    except InvalidScriptArchive:
        raise
    except (OSError, ValueError, KeyError, RuntimeError, NotImplementedError, zipfile.BadZipFile) as exc:
        raise InvalidScriptArchive(f"Invalid script ZIP: {exc}") from exc
