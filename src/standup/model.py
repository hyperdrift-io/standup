"""Pick the model provider from the environment: Vertex service account, Gemini key, else Bedrock."""
from __future__ import annotations

import base64
import json
import os


def resolve():
    model_id = os.environ.get("STANDUP_MODEL", "gemini-3.6-flash")
    sa_b64 = os.environ.get("GOOGLE_SA_KEY_B64")
    if sa_b64:
        from google import genai
        from google.oauth2 import service_account
        from strands.models.gemini import GeminiModel
        info = json.loads(base64.b64decode(sa_b64))
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        client = genai.Client(vertexai=True, project=os.environ.get("VERTEX_PROJECT", info["project_id"]),
                              location=os.environ.get("VERTEX_LOCATION", "global"), credentials=creds)
        return GeminiModel(client=client, model_id=model_id)
    if os.environ.get("GEMINI_API_KEY"):
        from strands.models.gemini import GeminiModel
        return GeminiModel(client_args={"api_key": os.environ["GEMINI_API_KEY"]}, model_id=model_id)
    return None  # Strands falls back to Bedrock with AWS credentials
