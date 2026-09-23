"""
mcp_client.py — milestone A of the LangChain/LangGraph harness.

Connects to the three existing MCP servers via langchain-mcp-adapters and
lists their tools as LangChain-compatible Tool objects.

IMPORTANT — two Python environments are involved here:
This script's own environment needs mcp v1.x (pulled in automatically by
langchain-mcp-adapters), which is NOT compatible with the v2 MCPServer class
tasks_mcp.py / calendar_mcp.py / finance_mcp.py are built on. That's fine —
SERVER_PYTHON below points at a *different* Python interpreter (the one that
already runs those three servers correctly), so the servers run in their own
environment while this script runs in its own. See the setup notes for how
to find that path.

Run it with:
    python mcp_client.py
"""
import asyncio
import os
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient

PROJECT_DIR = Path(__file__).parent

# The interpreter that already has mcp v2.x installed and correctly runs
# tasks_mcp.py, calendar_mcp.py, finance_mcp.py. Set this once with:
#   setx SERVER_PYTHON "C:\path\to\your\other\python.exe"
# (find the path with `where python`, run before activating this project's
# own venv). Kept as an env var rather than hardcoded, since this file is
# meant to be shared/committed and the path is specific to your machine.
SERVER_PYTHON = os.environ["SERVER_PYTHON"]

SERVERS = {
    "tasks": {
        "command": SERVER_PYTHON,
        "args": [str(PROJECT_DIR / "tasks_mcp.py")],
        "transport": "stdio",
    },
    "calendar": {
        "command": SERVER_PYTHON,
        "args": [str(PROJECT_DIR / "calendar_mcp.py")],
        "transport": "stdio",
    },
    "finance": {
        "command": SERVER_PYTHON,
        "args": [str(PROJECT_DIR / "finance_mcp.py")],
        "transport": "stdio",
    },
}


async def main() -> None:
    client = MultiServerMCPClient(SERVERS)
    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
