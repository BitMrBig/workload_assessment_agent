import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


DEFAULT_CONFIG = {
    "app": {
        "output_dir": "sessions",
        "max_clarify_rounds": 5,
        "effort_buffer_ratio": 0.2,
        "workload_unit": "person_day",
    },
    "llm": {
        "default": {
            "provider": "openai",
            "model": "gpt-5.4-mini",
            "temperature": 0.2,
        }
    },
    "providers": {
        "openai": {
            "api_key": "",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1",
        },
        "claude": {
            "api_key": "",
            "api_key_env": "ANTHROPIC_API_KEY",
            "base_url": "https://api.anthropic.com",
            "model": "claude-3-7-sonnet-latest",
        },
    },
}


def _deep_merge(base: dict, overrides: dict) -> dict:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_provider_keys(config: dict) -> dict:
    providers = config.get("providers", {})
    for name, provider in providers.items():
        api_key = provider.get("api_key", "").strip()
        env_name = provider.get("api_key_env", "").strip()
        if not api_key and env_name:
            api_key = os.getenv(env_name, "").strip()
        provider["resolved_api_key"] = api_key
        providers[name] = provider
    config["providers"] = providers
    return config


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. Copy config.example.toml to config.toml or pass --config."
        )

    user_config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    config = _deep_merge(DEFAULT_CONFIG, user_config)
    config = _resolve_provider_keys(config)
    workload_unit = config["app"].get("workload_unit", "person_day")
    if workload_unit not in {"person_day", "hour"}:
        raise ValueError("app.workload_unit must be either 'person_day' or 'hour'.")

    output_dir = Path(config["app"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    config["app"]["output_dir"] = str(output_dir)
    return config
