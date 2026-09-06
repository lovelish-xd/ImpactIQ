"""AI explanation layer for ImpactIQ.

Translates deterministic analyzer facts into natural-language explanations.
AI receives only structured facts; it never determines changes, dependencies,
impact, or numeric risk scores.

Uses only the Python standard library (urllib.request).
Supports Gemini API and OpenAI-compatible endpoints.
Gracefully returns unavailable state when no API key is configured.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any


def _load_env_file(filepath: Path) -> None:
    """Load key-value pairs from an env file if present."""
    if not filepath.is_file():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


def _ensure_env_loaded() -> None:
    """Check .env and .env.local in repo root."""
    root = Path(__file__).resolve().parents[2]
    _load_env_file(root / ".env")
    _load_env_file(root / ".env.local")


@dataclass(frozen=True, slots=True)
class AIExplanation:
    """Natural-language explanation of deterministic analysis results."""

    available: bool
    provider: str
    summary: str
    sections: dict[str, str] = dataclass_field(default_factory=dict)
    reason: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "provider": self.provider,
            "summary": self.summary,
            "sections": self.sections,
            "reason": self.reason,
            "message": self.message,
        }


def build_explanation_prompt(analysis_dict: dict[str, Any]) -> str:
    """Format structured analyzer facts into a strict explanatory prompt."""

    analysis = analysis_dict.get("analysis", analysis_dict)
    summary = analysis.get("summary", {})
    affected = analysis.get("affectedAssets", [])
    risk = analysis.get("risk", {})
    changes = analysis.get("changes", [])
    tests = analysis.get("regressionTests", [])
    dependencies = analysis.get("dependencies", {})

    facts = {
        "title": analysis.get("title", ""),
        "baseCommit": analysis.get("baseCommit", ""),
        "targetCommit": analysis.get("targetCommit", ""),
        "summary": summary,
        "change_count": len(changes),
        "changes": changes,
        "affected_assets": affected,
        "risk_score": risk.get("score", 0),
        "risk_level": risk.get("level", "Unknown"),
        "risk_drivers": risk.get("drivers", []),
        "dependency_edges": dependencies.get("edges", []),
        "recommended_tests": tests,
    }

    return (
        "You are an expert webMethods Integration Server architect. "
        "Explain the following deterministic change-impact analysis results.\n\n"
        "STRICT CONSTRAINTS:\n"
        "- Do NOT invent changes, dependencies, or tests not present in the facts.\n"
        "- Do NOT alter or calculate new risk scores; explain the given score.\n"
        "- Rely ONLY on the provided structured facts below.\n\n"
        f"FACTS:\n{json.dumps(facts, indent=2)}\n\n"
        "Respond ONLY with a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "summary": "Concise 2-sentence executive summary of the change and its scope",\n'
        '  "sections": {\n'
        '    "What Changed": "Clear explanation of the detected asset, field, mapping, and SQL changes",\n'
        '    "Impact Path": "Explanation of how changes propagate from modified assets to direct and transitive callers",\n'
        '    "Risk Analysis": "Why the risk level and score were assigned based on the drivers",\n'
        '    "Testing Rationale": "Explanation of why the recommended regression tests provide necessary coverage"\n'
        "  }\n"
        "}"
    )


def detect_configured_provider(
    api_key: str | None = None,
    provider: str | None = None,
    load_env: bool = True,
) -> tuple[str | None, str, str]:
    """Detect configured AI provider, API key, and model.

    Returns (provider_name, key, model) or (None, "", "") if unconfigured.
    Supports groq (auto-detected from gsk_ keys), xAI grok, gemini, and openai.
    """
    if load_env:
        _ensure_env_loaded()

    groq_key = api_key if provider == "groq" else (api_key or os.environ.get("GROQ_API_KEY", ""))
    grok_key = api_key if provider in ("grok", "xai") else (api_key or os.environ.get("GROK_API_KEY", "") or os.environ.get("XAI_API_KEY", ""))
    gemini_key = api_key if provider == "gemini" else (api_key or os.environ.get("GEMINI_API_KEY", ""))
    openai_key = api_key if provider == "openai" else (api_key or os.environ.get("OPENAI_API_KEY", ""))

    # Auto-detect if grok_key is actually a Groq key (starts with gsk_)
    if grok_key and grok_key.startswith("gsk_") and not groq_key:
        groq_key = grok_key
        grok_key = ""

    if provider == "groq" and groq_key:
        model = os.environ.get("GROQ_MODEL", os.environ.get("GROK_MODEL", "openai/gpt-oss-120b"))
        return ("groq", groq_key, model)
    elif provider in ("grok", "xai") and grok_key:
        model = os.environ.get("XAI_MODEL", os.environ.get("GROK_MODEL", "grok-2-latest"))
        return ("grok", grok_key, model)
    elif provider == "gemini" and gemini_key:
        model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        return ("gemini", gemini_key, model)
    elif provider == "openai" and openai_key:
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return ("openai", openai_key, model)
    elif provider:
        return (None, "", "")

    # Precedence when auto-detecting without explicit provider:
    if groq_key:
        model = os.environ.get("GROQ_MODEL", os.environ.get("GROK_MODEL", "openai/gpt-oss-120b"))
        return ("groq", groq_key, model)
    if grok_key:
        model = os.environ.get("XAI_MODEL", os.environ.get("GROK_MODEL", "grok-2-latest"))
        return ("grok", grok_key, model)
    if gemini_key:
        model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        return ("gemini", gemini_key, model)
    if openai_key:
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return ("openai", openai_key, model)

    return (None, "", "")


def get_ai_status() -> dict[str, Any]:
    """Check AI provider configuration status."""
    provider_name, key, model = detect_configured_provider()
    if not provider_name or not key:
        return {
            "configured": False,
            "provider": "None",
            "model": "",
            "message": (
                "AI explanation is optional. Configure GROK_API_KEY / GROQ_API_KEY, GEMINI_API_KEY, "
                "or OPENAI_API_KEY in .env.local to enable automated natural language insights."
            ),
        }

    display_names = {
        "groq": f"Groq ({model})",
        "grok": f"xAI Grok ({model})",
        "gemini": f"Google Gemini ({model})",
        "openai": f"OpenAI ({model})",
    }
    display = display_names.get(provider_name, f"{provider_name} ({model})")
    return {
        "configured": True,
        "provider": display,
        "model": model,
        "message": f"AI explanation ready using {display}.",
    }


def explain_analysis(
    analysis_data: dict[str, Any],
    api_key: str | None = None,
    provider: str | None = None,
    timeout: int = 15,
    load_env: bool = True,
) -> AIExplanation:
    """Generate an AI explanation for deterministic analysis results.

    If no API key is provided or found in environment variables, returns
    a graceful unavailable explanation. Never invents fake AI output.
    """

    if load_env:
        _ensure_env_loaded()

    chosen_provider, key, _ = detect_configured_provider(
        api_key=api_key, provider=provider, load_env=load_env
    )

    if not chosen_provider or not key:
        return AIExplanation(
            available=False,
            provider="none",
            summary="",
            sections={},
            reason="AI explanation not configured",
            message=(
                "AI explanation is optional. Configure GROK_API_KEY / GROQ_API_KEY, GEMINI_API_KEY, "
                "or OPENAI_API_KEY in .env.local or environment to enable natural language insights."
            ),
        )

    prompt = build_explanation_prompt(analysis_data)

    try:
        if chosen_provider == "groq":
            return _call_groq(prompt, key, timeout)
        elif chosen_provider in ("grok", "xai"):
            return _call_xai(prompt, key, timeout)
        elif chosen_provider == "gemini":
            return _call_gemini(prompt, key, timeout)
        elif chosen_provider == "openai":
            return _call_openai(prompt, key, timeout)
        else:
            return AIExplanation(
                available=False,
                provider=chosen_provider,
                summary="",
                sections={},
                reason="Unsupported AI provider",
                message=f"Provider '{chosen_provider}' is not supported.",
            )
    except urllib.error.HTTPError as exc:
        error_detail = ""
        try:
            err_json = json.loads(exc.read().decode("utf-8"))
            error_detail = (
                err_json.get("error", {}).get("message", "")
                if isinstance(err_json.get("error"), dict)
                else str(err_json.get("error", ""))
            )
        except Exception:
            pass
        msg = f"{chosen_provider.title()} API error ({exc.code}): {error_detail or exc.reason}"
        return AIExplanation(
            available=False,
            provider=chosen_provider,
            summary="",
            sections={},
            reason=f"API error ({exc.code})",
            message=msg,
        )
    except urllib.error.URLError as exc:
        return AIExplanation(
            available=False,
            provider=chosen_provider,
            summary="",
            sections={},
            reason="AI service unreachable",
            message=f"Network error connecting to {chosen_provider} API: {exc.reason}",
        )
    except Exception as exc:
        return AIExplanation(
            available=False,
            provider=chosen_provider,
            summary="",
            sections={},
            reason="AI explanation failed",
            message=f"Failed to generate explanation: {exc}",
        )


def _call_groq(prompt: str, api_key: str, timeout: int) -> AIExplanation:
    """Call Groq API using OpenAI-compatible endpoint."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    model = os.environ.get("GROQ_MODEL", os.environ.get("GROK_MODEL", "openai/gpt-oss-120b"))

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You explain webMethods change analysis in JSON format."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "ImpactIQ/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    text = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parse_ai_json_response(text, f"Groq ({model})")


def _call_xai(prompt: str, api_key: str, timeout: int) -> AIExplanation:
    """Call xAI Grok API using OpenAI-compatible endpoint."""
    url = "https://api.x.ai/v1/chat/completions"
    model = os.environ.get("GROK_MODEL", "grok-2-latest")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You explain webMethods change analysis in JSON format."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "ImpactIQ/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    text = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parse_ai_json_response(text, f"xAI Grok ({model})")


def _call_gemini(prompt: str, api_key: str, timeout: int) -> AIExplanation:
    """Call Google Gemini API using urllib."""
    model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ImpactIQ/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    # Extract text from Gemini response structure
    text = (
        resp_data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )

    return _parse_ai_json_response(text, "Google Gemini")


def _call_openai(prompt: str, api_key: str, timeout: int) -> AIExplanation:
    """Call OpenAI-compatible API using urllib."""
    base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You explain webMethods change analysis in JSON format."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "ImpactIQ/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    text = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parse_ai_json_response(text, "OpenAI")


def _parse_ai_json_response(raw_text: str, provider_name: str) -> AIExplanation:
    """Parse JSON text from an LLM response safely."""
    try:
        # Strip code fences if present
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        parsed = json.loads(clean_text)
        summary = parsed.get("summary", "")
        sections = parsed.get("sections", {})
        if not isinstance(sections, dict):
            sections = {}

        return AIExplanation(
            available=True,
            provider=provider_name,
            summary=summary,
            sections=sections,
            reason="Explanation generated successfully",
            message="",
        )
    except Exception as exc:
        return AIExplanation(
            available=False,
            provider=provider_name,
            summary="",
            sections={},
            reason="Malformed AI response",
            message=f"Could not parse AI output as JSON: {exc}",
        )
