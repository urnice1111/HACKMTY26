from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def api_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def model_name() -> str:
    return (os.getenv("OPENAI_MODEL") or "gpt-4o").strip()


def require_api_key() -> str:
    key = api_key()
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is empty. Add it to the .env file in the repo root:\n"
            "OPENAI_API_KEY=sk-..."
        )
    return key
