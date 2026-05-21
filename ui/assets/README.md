# Assets da UI

Diretório de arquivos estáticos referenciados pelo Streamlit.

## Arquivos esperados

| Arquivo | Quando aparece | Fallback |
|---|---|---|
| `iges-logo.png` | sidebar header, página de login (futuro) | texto "IGES-DF" |

## Como salvar o logo IGES

1. **Download**: salve a imagem PNG do logo (preferencialmente com fundo transparente) com nome **`iges-logo.png`**.
2. **Caminho**: copie para `ui/assets/iges-logo.png` na raiz do projeto.
3. **Redeploy** (se já estiver em produção):
   ```bash
   ./scripts/deploy_ui.sh
   ```

O `Dockerfile.ui` faz `COPY ui /app/ui` — qualquer arquivo dentro de `ui/` (incluindo `ui/assets/`) vai junto na imagem.

## Recomendações de imagem

- **Formato**: PNG com transparência, ou SVG
- **Largura mínima**: 200px (vai ser exibido em ~120px na sidebar)
- **Altura recomendada**: 60-80px
- **Peso**: < 50 KB
