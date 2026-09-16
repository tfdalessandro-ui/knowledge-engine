"""P7's model is the heaviest optional dependency in this project: a
multi-GB GGUF file this repo does not download for you (see HELP.md), on
top of llama-cpp-python needing a C++ build. Tests marked
`pytestmark = pytest.mark.requires_llm` are auto-skipped with a clear
reason when either the package or the model file is missing -- same
pattern as tests/kg (Memgraph) and tests/access (PostgreSQL), and
consistent with P7 itself being explicitly optional/skippable.
"""
import pytest

from config import get_settings


def _llm_available() -> bool:
    try:
        import llama_cpp  # noqa: F401
    except ImportError:
        return False
    return get_settings().llm_model_path.exists()


_AVAILABLE = _llm_available()


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_llm: needs llama-cpp-python and a downloaded GGUF model")


def pytest_collection_modifyitems(config, items):
    if _AVAILABLE:
        return
    skip = pytest.mark.skip(reason="llama-cpp-python and/or the GGUF model at OSE_LLM_MODEL_PATH is not available -- see HELP.md")
    for item in items:
        if "requires_llm" in item.keywords:
            item.add_marker(skip)
