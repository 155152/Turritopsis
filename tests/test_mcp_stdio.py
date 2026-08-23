from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_exposes_exactly_four_tools(data_path):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "turritopsis.cli", "serve", "--stdio", "--data", str(data_path)],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert [tool.name for tool in tools.tools] == [
                    "list_stages", "search_stages", "get_stage", "update_stage"
                ]
                result = await session.call_tool("list_stages", {})
                assert not result.isError

    asyncio.run(run())

