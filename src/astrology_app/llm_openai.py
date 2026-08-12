from __future__ import annotations

import json
import os
from datetime import date
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
    client_context: str | None = None,
    birth_input: dict[str, Any] | None = None,
    user_details: dict[str, Any] | None = None,
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
                            client_context=client_context,
                            birth_input=birth_input or {},
                            user_details=user_details or {},
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
        "Answer the user's astrology question using the supplied birth details and chart evidence. "
        "Please include details from both the past and the future when the chart evidence supports it."
    )


def _user_prompt(
    *,
    question: str,
    category: str,
    client_context: str | None,
    birth_input: dict[str, Any],
    user_details: dict[str, Any],
    reading_input: dict[str, Any],
    evidence: dict[str, Any],
) -> str:
    context_block = ""
    if client_context:
        context_block = (
            "Known life context / client facts:\n"
            f"{client_context.strip()}\n"
            "\n\n"
        )
    return (
        f"User question: {question}\n"
        f"Question category: {category}\n\n"
        f"Reading date: {date.today().isoformat()}\n\n"
        "Birth details:\n"
        f"{json.dumps(birth_input, indent=2)}\n\n"
        "All user details supplied:\n"
        f"{json.dumps(user_details, indent=2)}\n\n"
        f"{context_block}"
        "Selected chart evidence:\n"
        f"{json.dumps(evidence, indent=2)}\n\n"
        "Structured reading input:\n"
        f"{json.dumps(reading_input, indent=2)}\n\n"
        "Please keep the answers accurate based on the charts. Do not embellish the answers or "
        "sugarcoat them. The astrologer will be able to convey it in the right manner. Your job "
        "is to present the truth of the charts.\n"
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
