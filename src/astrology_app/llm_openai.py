from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIConfigurationError(RuntimeError):
    pass


class OpenAIRequestError(RuntimeError):
    pass


def openai_is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def generate_openai_answer(
    *,
    question: str,
    category: str,
    reading_input: dict[str, Any],
    evidence: dict[str, Any],
) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OpenAIConfigurationError(
            "OPENAI_API_KEY is not set. Add it to your environment to enable OpenAI answers."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    payload = {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": _developer_instructions(),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": _user_prompt(
                            question=question,
                            category=category,
                            reading_input=reading_input,
                            evidence=evidence,
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "text",
            }
        },
        "max_output_tokens": 700,
    }

    req = request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OpenAIRequestError(
            f"OpenAI API request failed with HTTP {exc.code}: {detail}"
        ) from exc
    except error.URLError as exc:
        raise OpenAIRequestError(f"OpenAI API request failed: {exc.reason}") from exc

    data = json.loads(raw)
    text = _extract_text_from_response(data)
    if not text:
        raise OpenAIRequestError("OpenAI API returned no text output.")
    return text.strip()


def _developer_instructions() -> str:
    return (
        "You are a Vedic astrology interpretation assistant. "
        "Use only the structured facts and signals supplied by the application. "
        "Do not invent additional chart placements, yogas, doshas, transits, or timing factors. "
        "Do not make deterministic or fear-based claims. "
        "If the evidence is mixed or weak, say so clearly. "
        "Do not claim an exact year unless the provided structured evidence clearly supports only a narrow timing window. "
        "Always cite the specific signals you relied on."
    )


def _user_prompt(
    *,
    question: str,
    category: str,
    reading_input: dict[str, Any],
    evidence: dict[str, Any],
) -> str:
    return (
        f"User question: {question}\n"
        f"Question category: {category}\n\n"
        "Selected chart evidence:\n"
        f"{json.dumps(evidence, indent=2)}\n\n"
        "Structured reading input:\n"
        f"{json.dumps(reading_input, indent=2)}\n\n"
        "Answer in this format:\n"
        "1. Summary\n"
        "2. Key evidence\n"
        "3. Timing windows\n"
        "4. Confidence\n"
        "5. Limits\n"
    )


def _extract_text_from_response(data: dict[str, Any]) -> str:
    texts: list[str] = []
    for output_item in data.get("output", []):
        if output_item.get("type") != "message":
            continue
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                text = content_item.get("text")
                if text:
                    texts.append(text)
    return "\n".join(texts)
