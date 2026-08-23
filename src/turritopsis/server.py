from __future__ import annotations

from mcp.server.fastmcp import FastMCP
import uvicorn

from .api import Turritopsis
from .config import resolve_data


def create_server(data_path=None, host: str = "127.0.0.1", port: int = 3013,
                  *, service: Turritopsis | None = None) -> FastMCP:
    service = service or Turritopsis(resolve_data(data_path))
    mcp = FastMCP("turritopsis", host=host, port=port)

    @mcp.tool()
    def list_stages(current: str = "") -> dict:
        """List currents, or compact stage metadata for one current. Never returns stage bodies."""
        return service.list_stages(current)

    @mcp.tool()
    def search_stages(query: str, match: str = "semantic", current: str = "",
                      stage_id: str = "", context: int = 2, limit: int = 8,
                      case_sensitive: bool = False) -> dict:
        """Route by weighted fields (semantic) or find literal lines (exact)."""
        return service.search_stages(query, match, current, stage_id, context, limit, case_sensitive)

    @mcp.tool()
    def get_stage(stage_id: str) -> dict:
        """Return one complete Stage, its metadata, and stage-local revision."""
        return service.get_stage(stage_id)

    @mcp.tool()
    def update_stage(stage_id: str, body: str, mode: str = "replace",
                     expected_revision: str = "", actor: str = "agent") -> dict:
        """Replace or append a Stage with optional optimistic revision checking."""
        return service.update_stage(stage_id, body, mode, expected_revision, actor)

    return mcp


def create_http_app(data_path=None, host: str = "127.0.0.1", port: int = 3013):
    from .web import attach_web

    service = Turritopsis(resolve_data(data_path))
    mcp = create_server(host=host, port=port, service=service)
    return attach_web(mcp.streamable_http_app(), service)


def serve(data_path=None, host: str = "127.0.0.1", port: int = 3013, stdio: bool = False):
    if stdio:
        mcp = create_server(data_path, host, port)
        mcp.run(transport="stdio")
    else:
        if host not in {"127.0.0.1", "localhost", "::1"}:
            print("Warning: Turritopsis has no authentication configured.\n"
                  "Anyone who can reach this server may read or modify project knowledge.")
        uvicorn.run(create_http_app(data_path, host, port), host=host, port=port, log_level="info")
