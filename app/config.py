from datetime import date
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Constituição P9 — DF only. Sufixo fixo de todos os índices.
DF_INDEX_SUFFIX = "df-brasilia"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: str = ""
    openai_planner_model: str = "gpt-4o"
    openai_narrator_model: str = "gpt-4o-mini"
    openai_router_model: str = "gpt-4o-mini"
    openai_validator_model: str = "gpt-4o"
    openai_critic_model: str = "gpt-4o-mini"

    # --- Fonte legada (SISREG-ES) — depreciada na virada v3, mantida por compat ---
    sisreg_base_url: str = "https://sisreg-es.saude.gov.br"
    sisreg_user: str = ""
    sisreg_pass: str = ""
    sisreg_uf_code_ibge: str = "53"  # para filter term codigo_uf_regulador
    sisreg_centrais_reguladoras: str = "530010"
    sisreg_request_timeout_seconds: int = 10

    # --- Fonte v3: API de vagas SISREG publicada pelo IGES ---
    # Gateway estilo Sensedia: auth por headers client_id/client_secret, GET-only.
    iges_vagas_url: str = "https://api.igesdf.org.br/iges/dados_vagas_sisreg"
    iges_vagas_client_id: str = ""
    iges_vagas_client_secret: str = ""
    iges_vagas_timeout_seconds: int = 60
    vagas_cache_path: str = "./data/vagas_cache.sqlite"

    app_mode: Literal["poc", "producao"] = "poc"
    poc_expires_at: date = date(2026, 7, 19)
    poc_pii_banner: str = "CONTÉM PII — uso interno IGES, distribuição proibida"

    audit_jsonl_path: str = "./audit.jsonl"
    log_level: str = "INFO"

    max_planner_attempts: int = 2
    max_narrator_attempts: int = 2

    @property
    def centrais_reguladoras_list(self) -> list[str]:
        return [c.strip() for c in self.sisreg_centrais_reguladoras.split(",") if c.strip()]


settings = Settings()
