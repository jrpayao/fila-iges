"""Cliente HTTP da API de vagas SISREG (IGES).

`GET https://api.igesdf.org.br/iges/dados_vagas_sisreg?mes=MM&ano=AAAA`

Fatos do endpoint (verificados 2026-07-07):
- Auth **por header** `client_id` + `client_secret`. Query-param/Basic -> 401.
- **GET-only** (POST/OPTIONS -> 405).
- Competencia SEM dado retorna **HTML** (um modal de erro) com HTTP 200 —
  NUNCA um JSON. Por isso validamos content-type/corpo antes de confiar.
- Competencia COM dado retorna uma lista JSON de registros (schema em RECORD_FIELDS).

Constituicao (analogo P13): esta camada e estritamente somente-leitura (so GET).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.config import settings

# Campos esperados em cada registro (para validacao defensiva do payload).
RECORD_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "cod_procedimento",
        "procedimento",
        "vagas_disponiveis",
        "data_extracao",
        "hospital_cnes",
        "hospital",
        "bloq_1",
        "bloq_retorno",
        "bloq_reserva",
        "ano_comp",
        "mes_comp",
        "ativ_1",
        "ativ_retorno",
        "ativ_reserva",
        "tipo",
    }
)


class VagasApiError(RuntimeError):
    """Falha generica de comunicacao/HTTP com a API de vagas."""


class VagasAuthError(VagasApiError):
    """401/400 — credenciais ausentes ou invalidas."""


class NoDataForCompetencia(VagasApiError):
    """A competencia pedida nao tem dados (a API devolve um HTML de erro)."""

    def __init__(self, mes: int, ano: int) -> None:
        self.mes = mes
        self.ano = ano
        super().__init__(f"Sem dados para competencia {mes:02d}/{ano}.")


@dataclass(frozen=True)
class _Auth:
    client_id: str
    client_secret: str


class VagasSisregClient:
    """GET-only client para o endpoint de vagas. Uso como context manager."""

    def __init__(
        self,
        *,
        url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self._url = url or settings.iges_vagas_url
        self._auth = _Auth(
            client_id or settings.iges_vagas_client_id,
            client_secret or settings.iges_vagas_client_secret,
        )
        self._client = httpx.Client(
            timeout=timeout or settings.iges_vagas_timeout_seconds,
            headers={
                "client_id": self._auth.client_id,
                "client_secret": self._auth.client_secret,
                "Accept": "application/json",
            },
        )

    # ----- API publica -----

    def fetch_competencia(self, mes: int, ano: int) -> list[dict]:
        """Baixa os registros de uma competencia. Lista de dicts (nunca None).

        Levanta:
        - `VagasAuthError` se credenciais faltarem/forem recusadas.
        - `NoDataForCompetencia` se a competencia nao tiver dados (HTML de erro).
        - `VagasApiError` para qualquer outra falha.
        """
        if not self._auth.client_id or not self._auth.client_secret:
            raise VagasAuthError(
                "iges_vagas_client_id/secret nao configurados (.env: "
                "IGES_VAGAS_CLIENT_ID / IGES_VAGAS_CLIENT_SECRET)."
            )

        try:
            resp = self._client.get(self._url, params={"mes": int(mes), "ano": int(ano)})
        except httpx.HTTPError as exc:  # rede/timeout
            raise VagasApiError(f"Falha de rede ao consultar {mes:02d}/{ano}: {exc}") from exc

        if resp.status_code in (400, 401, 403):
            raise VagasAuthError(
                f"HTTP {resp.status_code} em {mes:02d}/{ano}: {resp.text[:120]!r}"
            )
        if resp.status_code >= 400:
            raise VagasApiError(f"HTTP {resp.status_code} em {mes:02d}/{ano}: {resp.text[:120]!r}")

        return self._parse_payload(resp, mes, ano)

    # ----- internos -----

    @staticmethod
    def _parse_payload(resp: httpx.Response, mes: int, ano: int) -> list[dict]:
        """Confia no corpo so se for uma lista JSON de registros.

        Competencia vazia => a API responde 200 com HTML => NoDataForCompetencia.
        """
        ctype = resp.headers.get("content-type", "")
        body = resp.text.lstrip()
        looks_html = body[:1] == "<" or "text/html" in ctype

        if looks_html:
            raise NoDataForCompetencia(mes, ano)

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise VagasApiError(
                f"Resposta nao-JSON em {mes:02d}/{ano}: {body[:120]!r}"
            ) from exc

        if isinstance(data, dict):
            # Ex.: {"message": "Bad request"} ou {"error": "..."}.
            msg = data.get("message") or data.get("error") or str(data)[:120]
            raise VagasApiError(f"Erro da API em {mes:02d}/{ano}: {msg}")
        if not isinstance(data, list):
            raise VagasApiError(f"Formato inesperado em {mes:02d}/{ano}: {type(data).__name__}")

        return data

    # ----- lifecycle -----

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VagasSisregClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
