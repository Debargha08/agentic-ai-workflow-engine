from pathlib import Path


class FileSystemTool:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _safe_path(self, path: str | Path) -> Path:
        target = (self.root / path).resolve()

        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(
                "Access denied: path is outside the workspace."
            ) from exc

        return target

    def read_file(self, path: str) -> str:
        target = self._safe_path(path)

        if not target.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not target.is_file():
            raise IsADirectoryError(f"Not a file: {path}")

        return target.read_text(encoding="utf-8")
