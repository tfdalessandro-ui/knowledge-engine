"""Thin wrapper over llama-cpp-python (the P7 tech choice: a quantized
3-7B instruct model via llama.cpp, CPU-only). Lazy-loaded singleton, since
loading a multi-GB GGUF file is the expensive part and should happen once
per process, not per query.
"""
from __future__ import annotations

from pathlib import Path

from answer.repetition import truncate_on_repeat

_model = None
_model_path = None


def get_model(model_path: Path, n_ctx: int = 4096):
    global _model, _model_path
    if _model is None or _model_path != model_path:
        from llama_cpp import Llama

        _model = Llama(model_path=str(model_path), n_ctx=n_ctx, verbose=False)
        _model_path = model_path
    return _model


def generate(
    prompt: str,
    model_path: Path,
    n_ctx: int = 4096,
    max_tokens: int = 512,
    temperature: float = 0.0,
    repeat_penalty: float = 1.15,
) -> str:
    model = get_model(model_path, n_ctx=n_ctx)
    result = model(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        repeat_penalty=repeat_penalty,
        stop=["\n\nQuestion:", "\n\nPassages:"],
    )
    return truncate_on_repeat(result["choices"][0]["text"].strip())
