"""handover — what to do first when you come back to a project you left."""
from __future__ import annotations

import base64
import json
import os

from strands import Agent

from .tools import ci_status, list_projects, open_threads, project_snapshot

SYSTEM = """You are handover. Someone has just come back to a project they left weeks or months ago, and the first hour is usually lost to working out where they were.

Read the project's real state with your tools, then tell them the three things to do first.

How to choose the three:
1. Anything another person is waiting on outranks anything private. An open pull request with a review, an issue someone asked about, a red pipeline on the deploy branch.
2. Then anything that will be lost or painful later: uncommitted work, unpushed commits, a branch going stale against a moving main.
3. Then the thread they were actually pulling when they stopped, taken from the last commits.

Rules:
- Every item names the evidence you saw. "12 uncommitted files in src/, and main has moved 40 commits since" — not "there is uncommitted work".
- Say what to do, concretely, in one line. Not "consider reviewing".
- Estimate the minutes. Ten minutes and two hours are different decisions when someone has one evening.
- Three items. If there is genuinely only one, say one.
- Never imply they were careless for leaving it. People leave projects because life happens. Open with what is still standing, not what rotted.
- If the tools return nothing useful, say what you could not see rather than inventing a plan.

Finish with one line: what the project needs from them beyond tonight."""


def _model():
    """Vertex AI when a service account is present, otherwise the Gemini API key, otherwise Bedrock."""
    sa_b64 = os.environ.get("GOOGLE_SA_KEY_B64")
    model_id = os.environ.get("HANDOVER_MODEL", "gemini-3.6-flash")
    if sa_b64:
        from google import genai
        from google.oauth2 import service_account
        info = json.loads(base64.b64decode(sa_b64))
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        from strands.models.gemini import GeminiModel
        client = genai.Client(
            vertexai=True,
            project=os.environ.get("VERTEX_PROJECT", info["project_id"]),
            location=os.environ.get("VERTEX_LOCATION", "global"),
            credentials=creds,
        )
        return GeminiModel(client=client, model_id=model_id)
    if os.environ.get("GEMINI_API_KEY"):
        from strands.models.gemini import GeminiModel
        return GeminiModel(client_args={"api_key": os.environ["GEMINI_API_KEY"]}, model_id=model_id)
    return None  # Strands falls back to its Bedrock default


def build_agent() -> Agent:
    model = _model()
    kwargs = {
        "system_prompt": SYSTEM,
        "tools": [list_projects, project_snapshot, open_threads, ci_status],
        # The CLI prints the final answer itself; no streaming echo.
        "callback_handler": None,
    }
    if model is not None:
        kwargs["model"] = model
    return Agent(**kwargs)


def handover(target: str) -> str:
    """Run one handover over a repository path or a directory of them."""
    agent = build_agent()
    return str(agent(f"I'm coming back to this after a while: {target}. What are the three things I should do first?"))
