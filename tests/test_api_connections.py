#!/usr/bin/env python3
"""
test_api_connections.py — Quick API Connectivity Diagnostic Tool.

Tests API key validity and model endpoint reachability for:
  1. gpt-4o-mini (Native OpenAI)
  2. deepseek/deepseek-chat (OpenRouter / DeepSeek)
  3. meta-llama/llama-3.3-70b-instruct (OpenRouter / Meta)
  4. anthropic/claude-3.5-haiku (OpenRouter / Anthropic)
"""

import sys
import io
import os
from pathlib import Path
import pytest
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 on Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure backend directory is in python module search path
ROOT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Load environment variables from .env
load_dotenv(ROOT_DIR / ".env")

from judge_engine import get_evaluator_client

# This diagnostic performs paid external inference. It is deliberately absent
# from the ordinary/offline research test suite and can only run with an
# explicit operator opt-in in a separately authorized session.
if os.getenv("RUN_PROVIDER_CONNECTIVITY") != "1":
    pytestmark = pytest.mark.skip(reason="requires explicitly authorized real provider connectivity")

MODELS = [
    "gpt-4o-mini",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
    "anthropic/claude-3-haiku",
]

def test_connections():
    print("=" * 80)
    print("JUDGELAB API CONNECTIVITY TEST")
    print("=" * 80)

    for model_name in MODELS:
        print(f"\n[TESTING] Model: {model_name:<38} ... ", end="", flush=True)
        try:
            client, target_model = get_evaluator_client(model_name)
            response = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": "Say hello in one word."}],
                temperature=0.0,
                max_tokens=10,
            )
            text = (response.choices[0].message.content or "").strip()
            print(f"[SUCCESS] Response: '{text}'")
        except Exception as exc:
            print(f"[FAILED] Error: {str(exc)}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_connections()
