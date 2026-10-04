"""Tinker inference for Sugar's fine-tuned front-desk model.

Uses Tinker's OpenAI-compatible /completions endpoint with a prompt rendered exactly
like tinker_cookbook's `qwen3_disable_thinking` renderer (the format the LoRA was
trained on). Only needs httpx, so it also runs on small serverless hosts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from menu import SYSTEM_PROMPT

OAI_BASE = os.environ.get("TINKER_OAI_BASE", "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1")
TIMEOUT = float(os.environ.get("INFERENCE_TIMEOUT", "12"))


def model_path() -> str | None:
    if os.environ.get("TINKER_MODEL_PATH"):
        return os.environ["TINKER_MODEL_PATH"]
    for p in [Path(__file__).resolve().parent / "model.json", Path(__file__).resolve().parent.parent / "training/results/checkpoint.json"]:
        if p.exists():
            return json.loads(p.read_text()).get("sampler_path")
    return None


def enabled() -> bool:
    return bool(os.environ.get("TINKER_API_KEY")) and bool(model_path()) and os.environ.get("DISABLE_TINKER") != "1"


def render_prompt(history: list[dict]) -> str:
    """Qwen3 chat format with thinking disabled for the new turn."""
    parts = [f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"]
    for m in history:
        parts.append(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n")
    parts.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    return "".join(parts)


async def complete(history: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            f"{OAI_BASE}/completions",
            headers={"Authorization": f"Bearer {os.environ['TINKER_API_KEY']}"},
            json={"model": model_path(), "prompt": render_prompt(history), "max_tokens": 400,
                  "temperature": 0.3, "stop": ["<|im_end|>"]},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["text"].strip()
