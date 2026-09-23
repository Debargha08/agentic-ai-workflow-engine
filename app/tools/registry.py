from app.tools.code_search import CodeSearchTool
from app.tools.filesystem import FileSystemTool
from app.tools.python_executor import PythonExecutor
from app.tools.shell_executor import ShellExecutor


class ToolRegistry:
    def __init__(self, workspace_root: str):
        self.filesystem = FileSystemTool(workspace_root)
        self.code_search = CodeSearchTool(workspace_root)
        self.python_executor = PythonExecutor(workspace_root)
        self.shell_executor = ShellExecutor(workspace_root)

        self.tools = {
            "read_file": self.filesystem.read_file,
            "code_search": self.code_search.search,
            "python_execute": self.python_executor.execute,
            "shell_execute": self.shell_executor.execute,
        }

    def get(self, name: str):
        if name not in self.tools:
            raise KeyError(f"Unknown tool: {name}")

        return self.tools[name]
