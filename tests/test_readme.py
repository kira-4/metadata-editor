"""README must describe the service as it actually runs."""
from pathlib import Path

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")


def test_readme_has_no_gemini_leftovers():
    assert "gemini" not in README.lower()


def test_readme_documents_openrouter_settings():
    for var in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_FALLBACK_MODELS", "PUID"):
        assert var in README
