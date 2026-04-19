"""OpenAI client wrapper with structured output support."""

from __future__ import annotations

import logging

from openai import OpenAI
from pydantic import BaseModel

log = logging.getLogger(__name__)


def get_client() -> OpenAI:
    """Return a configured OpenAI client (reads OPENAI_API_KEY from env automatically)."""
    return OpenAI()


def parse_structured(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_message: str,
    schema: type[BaseModel],
) -> BaseModel:
    """Call the Responses API with structured output and return a validated Pydantic model.

    Raises openai.OpenAIError on API failures.
    Raises pydantic.ValidationError if the model returns an unexpected schema.
    """
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=schema,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("OpenAI returned a refusal or empty response")
    log.debug("AI call tokens: prompt=%d completion=%d",
              completion.usage.prompt_tokens, completion.usage.completion_tokens)
    return parsed
