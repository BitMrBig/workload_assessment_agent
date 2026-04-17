import json

from core.parser import extract_json_object


class LLMClient:
    def __init__(self, config: dict):
        self.config = config
        self.default_config = config["llm"]["default"]

    def generate_json(self, system_prompt: str, payload: dict) -> dict:
        provider_name = self.default_config["provider"]
        if provider_name == "openai":
            return self._call_openai(system_prompt, payload)
        if provider_name == "claude":
            return self._call_claude(system_prompt, payload)
        raise ValueError(f"Unsupported provider: {provider_name}")

    def _call_openai(self, system_prompt: str, payload: dict) -> dict:
        try:
            from openai import APIError, AuthenticationError, OpenAI, RateLimitError
        except ModuleNotFoundError as exc:
            raise RuntimeError("Missing dependency: openai") from exc

        provider = self.config["providers"]["openai"]
        api_key = provider.get("resolved_api_key", "")
        if not api_key:
            raise RuntimeError("OpenAI API key is missing. Set providers.openai.api_key or its env var.")

        client = OpenAI(api_key=api_key, base_url=provider.get("base_url"))
        try:
            response = client.chat.completions.create(
                model=self.default_config["model"],
                temperature=self.default_config["temperature"],
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
        except AuthenticationError as exc:
            raise RuntimeError("OpenAI authentication failed. Check the API key in config.toml.") from exc
        except RateLimitError as exc:
            raise RuntimeError(
                "OpenAI request failed due to rate limit or insufficient quota. "
                "Check billing, quota, and model availability for the configured API key."
            ) from exc
        except APIError as exc:
            raise RuntimeError(f"OpenAI API request failed: {exc}") from exc
        content = response.choices[0].message.content or "{}"
        return extract_json_object(content)

    def _call_claude(self, system_prompt: str, payload: dict) -> dict:
        try:
            from anthropic import Anthropic
            from anthropic import APIError as AnthropicAPIError
            from anthropic import AuthenticationError as AnthropicAuthenticationError
            from anthropic import RateLimitError as AnthropicRateLimitError
        except ModuleNotFoundError as exc:
            raise RuntimeError("Missing dependency: anthropic") from exc

        provider = self.config["providers"]["claude"]
        api_key = provider.get("resolved_api_key", "")
        if not api_key:
            raise RuntimeError("Claude API key is missing. Set providers.claude.api_key or its env var.")

        model = self.default_config.get("model") or provider.get("model")
        client = Anthropic(api_key=api_key, base_url=provider.get("base_url"))
        try:
            response = client.messages.create(
                model=model,
                temperature=self.default_config["temperature"],
                max_tokens=4000,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    }
                ],
            )
        except AnthropicAuthenticationError as exc:
            raise RuntimeError("Claude authentication failed. Check the API key in config.toml.") from exc
        except AnthropicRateLimitError as exc:
            raise RuntimeError(
                "Claude request failed due to rate limit or insufficient quota. "
                "Check billing, quota, and model availability for the configured API key."
            ) from exc
        except AnthropicAPIError as exc:
            raise RuntimeError(f"Claude API request failed: {exc}") from exc
        parts = []
        for block in response.content:
            if getattr(block, "type", "") == "text":
                parts.append(block.text)
        return extract_json_object("\n".join(parts))
