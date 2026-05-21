"""Cliente HTTP para o ES do SISREG.

Constituição P1: somente GET. Cliente recusa qualquer outro verbo.
Constituição P9: somente índices com sufixo DF_INDEX_SUFFIX.
"""

import httpx

from app.config import DF_INDEX_SUFFIX, settings


class SisregESClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.sisreg_base_url,
            auth=(settings.sisreg_user, settings.sisreg_pass),
            timeout=settings.sisreg_request_timeout_seconds,
            headers={"Content-Type": "application/json"},
        )

    def _assert_df_index(self, index: str) -> None:
        if not index.endswith(f"-{DF_INDEX_SUFFIX}"):
            raise ValueError(
                f"Indice fora do escopo DF: {index!r}. Deve terminar em -{DF_INDEX_SUFFIX!r}."
            )

    def search(self, index: str, body: dict) -> dict:
        """POST /_search — semanticamente GET em ES; body como parâmetro de consulta."""
        self._assert_df_index(index)
        path = f"/{index}/_search"
        response = self._client.post(path, json=body)
        response.raise_for_status()
        return response.json()

    def get_mapping(self, index: str) -> dict:
        """GET /<index>/_mapping — somente leitura."""
        self._assert_df_index(index)
        response = self._client.get(f"/{index}/_mapping")
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SisregESClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
