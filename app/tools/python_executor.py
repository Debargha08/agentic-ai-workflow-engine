import subprocess


class PythonExecutor:
    def __init__(
        self,
        workspace_root: str,
        timeout: int = 10,
    ):
        self.workspace_root = workspace_root
        self.timeout = timeout

    def execute(self, code: str) -> str:
        if not code.strip():
            raise ValueError("Python code cannot be empty.")

        try:
            process = subprocess.run(
                ["python3", "-c", code],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"Python execution exceeded {self.timeout} seconds."
            ) from exc

        output = []

        output.append(f"Exit code: {process.returncode}")

        if process.stdout:
            output.append(f"STDOUT:\n{process.stdout.strip()}")

        if process.stderr:
            output.append(f"STDERR:\n{process.stderr.strip()}")

        return "\n\n".join(output)
