from __future__ import annotations

from config.global_settings import load_global_settings, save_global_settings


def update_default_model(config, provider: str, default_model: str | None) -> None:
    if not default_model:
        if provider in config.default_models:
            del config.default_models[provider]
        if provider == config.llm_provider:
            config.llm_model = None
        gs = load_global_settings()
        if provider in gs.default_models:
            del gs.default_models[provider]
        if provider == gs.llm_provider:
            gs.llm_model = None
        save_global_settings(gs)
    else:
        from config.settings import set_default_model

        set_default_model(config, provider, default_model)
