"""OpenAI-SDK-based LLM provider abstraction supporting Groq and OpenRouter."""

from dataclasses import dataclass
import logging
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from app.config import GROQ_BASE_URL, OPENROUTER_BASE_URL, Settings
from app.schemas.chat import ProviderStatus

logger = logging.getLogger(__name__)


class LLMConfigurationError(Exception):
    """Raised when LLM provider configuration or API key is missing or invalid."""


class LLMProviderError(Exception):
    """Raised when an upstream LLM provider call fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        error_code: str = "provider_error",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True)
class ProviderConfig:
    """Resolved non-secret provider metadata."""

    provider: str
    model: str
    base_url: str
    api_key_env_var: str
    api_key: str | None


def resolve_provider_config(settings: Settings) -> ProviderConfig:
    """Resolve active provider settings without ever silently changing models."""
    if settings.llm_provider == "groq":
        return ProviderConfig(
            provider="groq",
            model=settings.groq_model,
            base_url=GROQ_BASE_URL,
            api_key_env_var="GROQ_API_KEY",
            api_key=settings.groq_api_key,
        )
    if settings.llm_provider == "openrouter":
        return ProviderConfig(
            provider="openrouter",
            model=settings.openrouter_model,
            base_url=OPENROUTER_BASE_URL,
            api_key_env_var="OPENROUTER_API_KEY",
            api_key=settings.openrouter_api_key,
        )
    raise LLMConfigurationError(
        f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. Use 'groq' or 'openrouter'."
    )


class LLMProvider:
    """Unified OpenAI-compatible client wrapper for Groq and OpenRouter."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.config = resolve_provider_config(settings)
        self._client = client

    def get_status(self) -> ProviderStatus:
        """Return safe provider status for health/settings pages without exposing keys."""
        configured = self.config.api_key is not None or self._client is not None
        if configured:
            msg = f"Configured for {self.config.provider} using model '{self.config.model}'."
        else:
            msg = f"Missing {self.config.api_key_env_var} in backend environment."
        return ProviderStatus(
            provider=self.config.provider,
            model=self.config.model,
            base_url=self.config.base_url,
            configured=configured,
            status_message=msg,
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        if not self.config.api_key:
            raise LLMConfigurationError(
                f"{self.config.api_key_env_var} is missing for provider "
                f"'{self.config.provider}'. Configure it in your backend .env file."
            )

        extra_headers: dict[str, str] = {}
        if self.config.provider == "openrouter":
            extra_headers = {
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "LifeDesk AI",
            }

        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=60.0,
            default_headers=extra_headers or None,
        )
        return self._client

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        """Send a tool-enabled chat completion request and return the assistant message."""
        client = self._get_client()

        try:
            response = client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
            )
        except AuthenticationError as exc:
            logger.warning("LLM authentication failed provider=%s", self.config.provider)
            raise LLMProviderError(
                f"Invalid API key for {self.config.provider}. Verify {self.config.api_key_env_var}.",
                status_code=502,
                error_code="invalid_api_key",
            ) from exc
        except RateLimitError as exc:
            logger.warning("LLM rate limit hit provider=%s model=%s", self.config.provider, self.config.model)
            raise LLMProviderError(
                f"Rate limit exceeded on {self.config.provider} ({self.config.model}). "
                "Please wait a moment and try again.",
                status_code=429,
                error_code="rate_limited",
            ) from exc
        except APITimeoutError as exc:
            logger.warning("LLM request timed out provider=%s", self.config.provider)
            raise LLMProviderError(
                f"Request to {self.config.provider} timed out.",
                status_code=504,
                error_code="timeout",
            ) from exc
        except APIConnectionError as exc:
            logger.warning("LLM connection failed provider=%s", self.config.provider)
            raise LLMProviderError(
                f"Failed to connect to {self.config.provider} at {self.config.base_url}.",
                status_code=502,
                error_code="connection_error",
            ) from exc
        except BadRequestError as exc:
            detail = str(exc)
            lowered = detail.lower()
            if any(token in lowered for token in ("tool", "function", "tool_choice", "tool_use")):
                raise LLMProviderError(
                    f"Model '{self.config.model}' on {self.config.provider} rejected tool calling: {detail}",
                    status_code=502,
                    error_code="tool_calling_unsupported",
                ) from exc
            if "model" in lowered or "not found" in lowered:
                raise LLMProviderError(
                    f"Configured model '{self.config.model}' is unavailable on {self.config.provider}.",
                    status_code=502,
                    error_code="model_unavailable",
                ) from exc
            raise LLMProviderError(
                f"Bad request to {self.config.provider}: {detail}",
                status_code=502,
                error_code="bad_request",
            ) from exc
        except APIStatusError as exc:
            status = getattr(exc, "status_code", 502) or 502
            if status == 404:
                raise LLMProviderError(
                    f"Model '{self.config.model}' was not found on {self.config.provider}.",
                    status_code=502,
                    error_code="model_unavailable",
                ) from exc
            raise LLMProviderError(
                f"{self.config.provider} API error (HTTP {status}): {exc}",
                status_code=502,
                error_code="provider_error",
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"Unexpected error calling {self.config.provider}: {exc}",
                status_code=502,
                error_code="provider_error",
            ) from exc

        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMProviderError(
                f"{self.config.provider} returned an empty response with no choices.",
                status_code=502,
                error_code="malformed_response",
            )

        message = getattr(choices[0], "message", None)
        if message is None:
            raise LLMProviderError(
                f"{self.config.provider} returned a malformed choice without a message.",
                status_code=502,
                error_code="malformed_response",
            )

        return message
