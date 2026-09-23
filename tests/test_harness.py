"""
Standalone test for harness.py.

Covers:
1. extract_text() against both a plain string and the list-of-content-blocks
   shape Gemini returns when a thought signature is attached — this is a
   direct regression test for a real bug: the first version of this harness
   sent the raw content list (including the signature) to Telegram and got
   a 400 error back.
2. The full agent loop, with real tool execution against the actual MCP
   servers and only the model's replies simulated.

Run it from the project root, with SERVER_PYTHON set and the project's
.venv active:
    python tests/test_harness.py
"""
import asyncio
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_mcp_adapters.client import MultiServerMCPClient

import harness


def test_extract_text():
    print("== extract_text(): regression test for the Telegram bug ==")

    # The shape that broke it: a list of content blocks with a giant
    # signature riding alongside the actual text.
    broken_content = [
        {
            "type": "text",
            "text": "You have one task due today.",
            "extras": {"signature": "abc123" * 100},
        }
    ]
    result = harness.extract_text(broken_content)
    assert result == "You have one task due today."
    assert "signature" not in result
    assert len(result) < 100

    # Plain strings must still pass through unchanged.
    assert harness.extract_text("plain string answer") == "plain string answer"

    print("PASS\n")


class ScriptedFakeModel(BaseChatModel):
    """A minimal fake chat model supporting bind_tools(), returning
    pre-scripted responses in order — enough to test the agent loop
    without a live API call."""

    responses: List[AIMessage] = []
    _call_count: int = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        response = self.responses[self._call_count]
        self._call_count += 1
        return ChatResult(generations=[ChatGeneration(message=response)])

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"


async def test_full_loop():
    print("== Full agent loop: mocked model, real tool execution ==")
    client = MultiServerMCPClient(harness.SERVERS)
    tools = await client.get_tools()
    assert len(tools) == 10

    fake_model = ScriptedFakeModel(
        responses=[
            AIMessage(content="", tool_calls=[ToolCall(name="list_tasks", args={}, id="c1")]),
            AIMessage(content="You have three tasks due."),
        ]
    )

    agent = create_agent(fake_model, tools)
    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "What tasks do I have?"}]}
    )

    final = harness.extract_text(response["messages"][-1].content)
    assert final == "You have three tasks due."

    tool_messages = [m for m in response["messages"] if type(m).__name__ == "ToolMessage"]
    assert len(tool_messages) == 1
    assert "Finish MCP tutorial" in str(tool_messages[0].content)

    print("PASS\n")


async def main():
    test_extract_text()
    await test_full_loop()


if __name__ == "__main__":
    asyncio.run(main())
