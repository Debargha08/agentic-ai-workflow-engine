from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool


class ReadFileArgs(BaseModel):
    path: str = Field(
        description="Path to a file inside the approved project workspace."
    )


class CodeSearchArgs(BaseModel):
    query: str = Field(
        description="Text to search for in project source files."
    )
    path: str = Field(
        default=".",
        description="Directory or file inside the approved project workspace."
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of matching lines to return."
    )


class PythonExecuteArgs(BaseModel):
    code: str = Field(
        description="Python code to execute for analysis or validation."
    )


class ShellExecuteArgs(BaseModel):
    command: str = Field(
        description=(
            "Safe shell command for repository inspection or testing. "
            "Allowed commands include pytest, git status, git diff, "
            "git log, and python3 --version."
        )
    )


def _read_file_placeholder(path: str) -> str:
    return ""


def _code_search_placeholder(
    query: str,
    path: str = ".",
    max_results: int = 10,
) -> str:
    return ""


def _python_execute_placeholder(code: str) -> str:
    return ""


def _shell_execute_placeholder(command: str) -> str:
    return ""


read_file = StructuredTool.from_function(
    func=_read_file_placeholder,
    name="read_file",
    description=("Read a specific project file. Use a relative path inside the workspace, such as app/workflow/state.py. Never use .. or parent directories."),
    args_schema=ReadFileArgs,
)


code_search = StructuredTool.from_function(
    func=_code_search_placeholder,
    name="code_search",
    description=("Search source files using a relative workspace path. Start with path=. when the location is unknown. Never use .. or parent directories."),
    args_schema=CodeSearchArgs,
)


python_execute = StructuredTool.from_function(
    func=_python_execute_placeholder,
    name="python_execute",
    description=(
        "Execute a short Python program for analysis or validation. "
        "The program is subject to an execution timeout."
    ),
    args_schema=PythonExecuteArgs,
)


shell_execute = StructuredTool.from_function(
    func=_shell_execute_placeholder,
    name="shell_execute",
    description=(
        "Execute a restricted repository command. "
        "Use for git status, git diff, git log, pytest, "
        "or python3 --version."
    ),
    args_schema=ShellExecuteArgs,
)
