"""Unit tests for LLMProvider switching and error handling."""

from types import SimpleNamespace
from typing import Any

import httpx
from openai import APITimeoutError, AuthenticationError, BadRequestError, RateLimitError
import pytest

from app.agent.llm_provider import (
    LLMConfigurationError,
    LLMProvider,
    LLMProviderError,
    resolve_provider_config,
)
from app.config import GROQ_BASE_URL, OPENROUTER_BASE_URL, Settings


def _make_response(status_code: int) -> httpx.Response:
    req = httpx.Request("POST", "https://example.com/v1/chat/completions")
    return httpx.Response(status_code=status_code, request=req)


def test_provider_switching_resolves_groq_and_openrouter() -> None:
    groq_settings = Settings(
        llm_provider="groq",
        groq_api_key="gsk_test",
        groq_model="openai/gpt-oss-20b",
    )
    groq_cfg = resolve_provider_config(groq_settings)
    assert groq_cfg.provider == "groq"
    assert groq_cfg.base_url == GROQ_BASE_URL
    assert groq_cfg.model == "openai/gpt-oss-20b"

    or_settings = Settings(
        llm_provider="openrouter",
        openrouter_api_key="sk_or_test",
        openrouter_model="openrouter/free",
    )
    or_cfg = resolve_provider_config(or_settings)
    assert or_cfg.provider == "openrouter"
    assert or_cfg.base_url == OPENROUTER_BASE_URL
    assert or_cfg.model == "openrouter/free"


def test_missing_api_key_raises_clear_configuration_error() -> None:
    settings = Settings(llm_provider="groq", groq_api_key=None)
    provider = LLMProvider(settings)
    with pytest.raises(LLMConfigurationError) as exc_info:
        provider.create_chat_completion(messages=[], tools=[])
    assert "GROQ_API_KEY" in str(exc_info.value)


def test_provider_maps_auth_rate_limit_timeout_and_unsupported_tool_errors() -> None:
    class FailingClient:
        def __init__(self, exc: Exception) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_kwargs: (_ for _ in ()).throw(exc))
            )

    settings = Settings(llm_provider="openrouter", openrouter_api_key="sk_or_test")

    auth_err = AuthenticationError("invalid key", response=_make_response(401), body=None)
    with pytest.raises(LLMProviderError) as exc_auth:
        LLMProvider(settings, client=FailingClient(auth_err)).create_chat_completion(
            messages=[], tools=[]
        )
    assert exc_auth.value.error_code == "invalid_api_key"

    rate_err = RateLimitError("too many requests", response=_make_response(429), body=None)
    with pytest.raises(LLMProviderError) as exc_rate:
        LLMProvider(settings, client=FailingClient(rate_err)).create_chat_completion(
            messages=[], tools=[]
        )
    assert exc_rate.value.status_code == 429
    assert exc_rate.value.error_code == "rate_limited"

    timeout_err = APITimeoutError(request=httpx.Request("POST", "https://example.com"))
    with pytest.raises(LLMProviderError) as exc_timeout:
        LLMProvider(settings, client=FailingClient(timeout_err)).create_chat_completion(
            messages=[], tools=[]
        )
    assert exc_timeout.value.status_code == 504

    tool_err = BadRequestError(
        "This model does not support tool calling",
        response=_make_response(400),
        body=None,
    )
    with pytest.raises(LLMProviderError) as exc_tool:
        LLMProvider(settings, client=FailingClient(tool_err)).create_chat_completion(
            messages=[], tools=[]
        )
    assert exc_tool.value.error_code == "tool_calling_unsupported"
    assert "openrouter/free" in str(exc_tool.value)


def test_status_never_exposes_api_keys() -> None:
    secret = "gsk_super_secret_value_12345"
    settings = Settings(llm_provider="groq", groq_api_key=secret)
    status = LLMProvider(settings).get_status()
    assert status.configured is True
    assert secret not in status.model_dump_json()
