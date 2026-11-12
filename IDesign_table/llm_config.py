"""Load AutoGen credentials without embedding secrets in source files."""

import json
import os
from pathlib import Path


def load_config_list():
    """Prefer environment credentials; accept an ignored local JSON config."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()

    if api_key:
        configs = [{
            "model": model or "gpt-4.1-mini-2025-04-14",
            "api_key": api_key,
        }]
    else:
        path = Path(__file__).with_name("OAI_CONFIG_LIST.json")
        if not path.is_file():
            raise ValueError(
                "Set OPENAI_API_KEY or create OAI_CONFIG_LIST.json from the example."
            )
        with path.open(encoding="utf-8") as handle:
            configs = json.load(handle)

    if not isinstance(configs, list) or not configs:
        raise ValueError("OAI_CONFIG_LIST.json must contain a non-empty list.")
    for config in configs:
        if not isinstance(config, dict):
            raise ValueError("Each LLM configuration must be a JSON object.")
        key = config.get("api_key", "")
        if not isinstance(key, str) or not key.strip() or key == "YOUR_API_KEY":
            raise ValueError("Set OPENAI_API_KEY or replace the local API key placeholder.")
        if model:
            config["model"] = model
        if not config.get("model"):
            raise ValueError("Each LLM configuration must specify a model.")
        if base_url:
            config["base_url"] = base_url
    return configs
