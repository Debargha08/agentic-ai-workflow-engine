from app.tools.registry import ToolRegistry
from app.workflow.state import ToolRequest, ToolResult


class ToolExecutor:
    def __init__(self, workspace_root: str):
        self.registry = ToolRegistry(workspace_root)

    @staticmethod
    def _normalize_args(args: dict) -> dict:
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be a dictionary.")

        if (
            set(args.keys()) == {"object"}
            and isinstance(args["object"], dict)
        ):
            return args["object"]

        return args

    def execute(self, request: ToolRequest) -> ToolResult:
        name = request.get("name", "")
        request_args = request.get("args", {})
        request_id = request.get("id", "")

        try:
            args = self._normalize_args(request_args)
            tool = self.registry.get(name)

            result = tool(**args)

            return {
                "name": name,
                "success": True,
                "result": str(result),
                "error": "",
                "id": request_id,
            }

        except Exception as exc:
            return {
                "name": name,
                "success": False,
                "result": "",
                "error": str(exc),
                "id": request_id,
            }

    def execute_all(
        self,
        requests: list[ToolRequest],
    ) -> list[ToolResult]:
        return [
            self.execute(request)
            for request in requests
        ]
