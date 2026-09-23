import shlex
import subprocess
from pathlib import Path


class ShellExecutor:
    ALLOWED_COMMANDS = {
        "pytest",
        "python3",
        "git",
    }

    ALLOWED_GIT_SUBCOMMANDS = {
        "status",
        "diff",
        "log",
    }

    BLOCKED_GIT_FLAGS = {
        "--git-dir",
        "--work-tree",
        "-C",
    }

    def __init__(
        self,
        workspace_root: str | Path,
        timeout: int = 10,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.timeout = timeout
        self.max_output_chars = 12000

    def _validate_command(self, command: str) -> list[str]:
        if not command.strip():
            raise ValueError("Shell command cannot be empty.")

        try:
            parts = shlex.split(command)
        except ValueError as exc:
            raise ValueError(
                f"Invalid shell command syntax: {exc}"
            ) from exc

        if not parts:
            raise ValueError("Shell command cannot be empty.")

        executable = Path(parts[0]).name

        if executable not in self.ALLOWED_COMMANDS:
            raise PermissionError(
                f"Command not allowed: {executable}"
            )

        if executable == "git":
            if len(parts) < 2:
                raise PermissionError(
                    "Git subcommand is required."
                )

            if any(
                flag in parts
                for flag in self.BLOCKED_GIT_FLAGS
            ):
                raise PermissionError(
                    "Git repository redirection is not allowed."
                )

            if parts[1] not in self.ALLOWED_GIT_SUBCOMMANDS:
                raise PermissionError(
                    f"Git subcommand not allowed: {parts[1]}"
                )

        elif executable == "python3":
            if len(parts) != 2 or parts[1] not in {
                "--version",
                "-V",
            }:
                raise PermissionError(
                    "Only 'python3 --version' is allowed through shell_execute."
                )

        return parts

    def execute(self, command: str) -> str:
        parts = self._validate_command(command)

        try:
            process = subprocess.run(
                parts,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )

        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"Shell execution exceeded {self.timeout} seconds."
            ) from exc

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()

        if len(stdout) > self.max_output_chars:
            stdout = (
                stdout[:self.max_output_chars]
                + "\n[STDOUT TRUNCATED]"
            )

        if len(stderr) > self.max_output_chars:
            stderr = (
                stderr[:self.max_output_chars]
                + "\n[STDERR TRUNCATED]"
            )

        output = [
            f"Command: {' '.join(parts)}",
            f"Exit code: {process.returncode}",
        ]

        if stdout:
            output.append(f"STDOUT:\n{stdout}")

        if stderr:
            output.append(f"STDERR:\n{stderr}")

        return "\n\n".join(output)
