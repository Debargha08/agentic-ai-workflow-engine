import re
from pathlib import Path


class CodeSearchTool:
    EXCLUDED_DIRS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
    }

    EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".json",
        ".yaml",
        ".yml",
        ".md",
    }

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _safe_path(self, path: str | Path) -> Path:
        requested = Path(path).expanduser()

        # Accept absolute paths only when they are still inside
        # the configured workspace.
        if requested.is_absolute():
            target = requested.resolve()
        else:
            target = (self.root / requested).resolve()

        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(
                "Access denied: search path is outside the workspace."
            ) from exc

        return target

    def search(
        self,
        query: str,
        path: str = ".",
        max_results: int = 20,
    ) -> str:
        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        if max_results <= 0:
            raise ValueError("max_results must be greater than zero.")

        search_path = self._safe_path(path)

        if not search_path.exists():
            raise FileNotFoundError(
                f"Search path not found: {path}"
            )

        if search_path.is_file():
            files = [search_path]
        elif search_path.is_dir():
            files = search_path.rglob("*")
        else:
            raise ValueError(f"Invalid search path: {path}")

        query_lower = query.lower()
        matches = []

        for file_path in files:
            if not file_path.is_file():
                continue

            if any(
                part in self.EXCLUDED_DIRS
                for part in file_path.parts
            ):
                continue

            if file_path.suffix.lower() not in self.EXTENSIONS:
                continue

            try:
                lines = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).splitlines()
            except OSError:
                continue

            for line_number, line in enumerate(lines, start=1):
                if query_lower not in line.lower():
                    continue

                stripped = line.strip()

                if re.search(
                    rf"^\s*class\s+{re.escape(query)}\b",
                    stripped,
                    re.IGNORECASE,
                ):
                    priority = 0
                elif re.search(
                    rf"^\s*def\s+{re.escape(query)}\b",
                    stripped,
                    re.IGNORECASE,
                ):
                    priority = 0
                elif query_lower in file_path.stem.lower():
                    priority = 1
                elif re.match(
                    rf"^\s*(from|import)\b.*\b{re.escape(query)}\b",
                    stripped,
                    re.IGNORECASE,
                ):
                    priority = 3
                else:
                    priority = 2

                relative_path = file_path.relative_to(self.root)

                matches.append(
                    (
                        priority,
                        str(relative_path),
                        line_number,
                        f"{relative_path}:{line_number}: {stripped}",
                    )
                )

        matches.sort(key=lambda item: (item[0], item[1], item[2]))

        if not matches:
            return "No matches found."

        return "\n".join(
            item[3]
            for item in matches[:max_results]
        )
