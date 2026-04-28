"""Device script version management — upload, version, download."""
from pathlib import Path

from app.config import SERVER_DIR


class ScriptService:
    def __init__(self, script_dir: Path | None = None, version_file: Path | None = None):
        self._script_dir = script_dir or (SERVER_DIR / "scripts")
        self._version_file = version_file or (self._script_dir / "version.txt")

    def _ensure_dir(self):
        self._script_dir.mkdir(parents=True, exist_ok=True)

    def get_version(self) -> str:
        """Return current script version. Defaults to '0.0.0'."""
        if self._version_file.exists():
            return self._version_file.read_text(encoding="utf-8").strip()
        return "0.0.0"

    def _bump_version(self) -> str:
        """Bump patch version: 1.0.0 -> 1.0.1."""
        current = self.get_version()
        parts = current.split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            parts[2] = str(int(parts[2]) + 1)
        else:
            parts = ["0", "0", "1"]
        new_version = ".".join(parts)
        self._version_file.write_text(new_version, encoding="utf-8")
        return new_version

    def upload_script(self, fileobj) -> str:
        """Upload a new script zip, bump version, return new version string."""
        self._ensure_dir()
        script_path = self._script_dir / "device-script.zip"
        content = fileobj.read() if hasattr(fileobj, "read") else fileobj
        script_path.write_bytes(content)
        return self._bump_version()

    def download_script(self) -> bytes | None:
        """Download current script zip. Returns None if no script exists."""
        script_path = self._script_dir / "device-script.zip"
        if not script_path.exists():
            return None
        return script_path.read_bytes()


script_service = ScriptService()
