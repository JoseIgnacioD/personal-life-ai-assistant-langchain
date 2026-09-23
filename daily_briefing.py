"""
daily_briefing.py: runs the LangChain/LangGraph harness.py headlessly, then
sends the resulting briefing to Telegram.

IMPORTANT: this script must itself be run with the project's .venv Python
(the one with langchain, langgraph, langchain-mcp-adapters installed) —
it uses sys.executable to spawn harness.py, so whatever interpreter runs
this file is what harness.py will run under too. When setting this up in
Task Scheduler, point it at .venv\\Scripts\\python.exe, not your system
Python (that one is for the MCP servers harness.py spawns internally, and
is set separately via harness.py's own SERVER_PYTHON constant).

Run it by hand first to test, with the .venv active:
    python daily_briefing.py

Needs two environment variables set beforehand (see the Telegram setup
steps from the earlier projects):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
"""
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
HARNESS_PATH = PROJECT_DIR / "harness.py"

PROMPT = (
    "Give me a short daily briefing: any tasks due today or overdue, what's "
    "on my calendar today, and my current account balance. Keep it under "
    "100 words, plain text, no markdown formatting."
)


def run_harness() -> str:
    """Run harness.py headlessly and return its final text reply.

    harness.py prints its tool-call trace to stderr and only the final
    answer to stdout, so stdout alone is exactly what should go to Telegram.
    """
    result = subprocess.run(
        [sys.executable, str(HARNESS_PATH), "-p", PROMPT],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"harness.py exited with code {result.returncode}:\n{result.stderr}")
    return result.stdout.strip()


def send_telegram(message: str) -> None:
    """Send a plain-text message through the configured Telegram bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError(
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables first."
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Telegram API returned status {response.status}")


def main() -> None:
    briefing = run_harness()
    print(briefing)
    send_telegram(briefing)


if __name__ == "__main__":
    main()
