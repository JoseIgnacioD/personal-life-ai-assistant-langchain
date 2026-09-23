"""
harness.py — milestone B of the LangChain/LangGraph harness.

Builds a full agent using langchain.agents.create_agent (LangGraph's own
create_react_agent is deprecated as of LangGraph 1.0 in favor of this),
wired to the same three MCP servers via langchain-mcp-adapters, with Gemini
as the model. Unlike the hand-built harness, there's no separate "see the
tool call without executing it" step — create_agent already IS the full
loop: call the model, execute whatever tools it asks for, feed results
back, repeat until it answers with no more tool calls.

Uses langchain-google-genai's native integration rather than ChatOpenAI
pointed at Gemini's OpenAI-compatible endpoint. This isn't a style choice —
Gemini's newer models attach an opaque "thought_signature" to each function
call that must be echoed back on the next turn, and the generic OpenAI-
compatible layer has no field for it, causing multi-turn tool calls to fail
with a 400 error after the first tool call. Google's own SDK (which this
integration wraps) round-trips it correctly.

Run it with:
    python harness.py
"""
import asyncio
import os
import sys

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from mcp_client import SERVERS


def get_model() -> ChatGoogleGenerativeAI:
    """Google's native SDK (which this integration wraps) handles the
    thought_signature round-trip automatically — unlike ChatOpenAI pointed
    at the OpenAI-compatible endpoint, which has no field for it."""
    return ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        google_api_key=os.environ["GEMINI_API_KEY"],
    )


def extract_text(content) -> str:
    """AIMessage.content is usually a plain string, but Gemini's models
    return a list of content blocks instead when a thought signature is
    attached — e.g. [{'type': 'text', 'text': '...', 'extras': {...}}].
    Pull out just the actual text, discarding the signature and any other
    metadata riding along with it.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def print_tool_trace(messages) -> None:
    """Print which tools were called, to stderr — mirrors the hand-built
    harness's convention, so daily_briefing.py's stdout stays clean. Unlike
    the hand-built version this is printed after the fact (create_agent
    doesn't expose a mid-loop hook the way the manual run_turn loop did),
    but only for calls not already reported in a prior turn.
    """
    for m in messages:
        if type(m).__name__ == "AIMessage" and getattr(m, "tool_calls", None):
            for call in m.tool_calls:
                print(f"  -> calling {call['name']}({call['args']})", file=sys.stderr)


async def interactive_loop(agent) -> None:
    print("LangChain/LangGraph harness ready. Type a message (Ctrl+C to exit).\n")
    messages: list = []
    reported = 0
    while True:
        try:
            prompt = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return
        if not prompt.strip():
            continue
        messages.append({"role": "user", "content": prompt})
        response = await agent.ainvoke({"messages": messages})
        messages = response["messages"]  # carry the full updated history forward
        print_tool_trace(messages[reported:])
        reported = len(messages)
        print(extract_text(messages[-1].content), "\n")


async def main() -> None:
    client = MultiServerMCPClient(SERVERS)
    tools = await client.get_tools()

    model = get_model()
    agent = create_agent(model, tools)

    if len(sys.argv) > 2 and sys.argv[1] == "-p":
        prompt = sys.argv[2]
        response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        print_tool_trace(response["messages"])
        print(extract_text(response["messages"][-1].content))
    else:
        await interactive_loop(agent)


if __name__ == "__main__":
    asyncio.run(main())
