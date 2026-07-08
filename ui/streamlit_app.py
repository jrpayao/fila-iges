"""UI Streamlit — Fila Eletiva DF (IGES-DF / ZELLO).

Layout publico para coordenadores CGRA e gestores IGES.
Esconde detalhes de implementacao (pipeline multi-agente, templates) que
ficam disponiveis apenas em expansores "Detalhes da consulta".
"""

import os
import time
from datetime import date
from pathlib import Path

import httpx
import streamlit as st

# ===== Config =====
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
_API_AUTH_USER = os.environ.get("API_AUTH_USER", "")
_API_AUTH_PASS = os.environ.get("API_AUTH_PASS", "")
_AUTH = (_API_AUTH_USER, _API_AUTH_PASS) if _API_AUTH_USER else None

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH = ASSETS_DIR / "iges-logo.png"

# Paleta IGES (extraida do logo)
COLOR_PRIMARY = "#1A6FA8"   # azul IGES
COLOR_ACCENT = "#37B8C5"    # turquesa "DF"
COLOR_GREEN = "#9DCC23"     # verde do logo
COLOR_YELLOW = "#FAD61E"    # amarelo do logo
COLOR_ORANGE = "#E8851E"    # laranja do logo

st.set_page_config(
    page_title="Fila Eletiva DF — IGES-DF",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "**Fila Eletiva DF** — Painel analítico da fila de regulação do SISREG-DF.\n\n"
            "IGES-DF em parceria com a ZELLO."
        )
    },
)

# Logo oficial no header da sidebar (se PNG existir)
if LOGO_PATH.exists():
    try:
        st.logo(str(LOGO_PATH), size="large", link=None)
    except TypeError:
        # Streamlit antigo pode nao ter o param `link`
        st.logo(str(LOGO_PATH))

# ===== CSS =====
st.markdown(
    f"""
<style>
/* Esconder branding do Streamlit */
#MainMenu, footer {{visibility: hidden;}}
header[data-testid="stHeader"] {{background: transparent;}}

/* Container principal */
.block-container {{
    padding-top: 2rem;
    padding-bottom: 6rem;
    max-width: 1100px;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    background-color: #F8FAFC;
    border-right: 1px solid #E5E7EB;
}}
[data-testid="stSidebar"] .stMarkdown h3 {{
    font-size: 0.85rem;
    color: #4B5563;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    margin-top: 0.5rem;
    margin-bottom: 0.75rem;
}}

/* Cabecalho */
.fe-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 3px solid {COLOR_PRIMARY};
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    gap: 1.5rem;
}}
.fe-header-text {{flex: 1;}}
.fe-title {{
    color: {COLOR_PRIMARY};
    font-size: 2rem;
    font-weight: 700;
    margin: 0;
    line-height: 1.2;
    letter-spacing: -0.02em;
}}
.fe-subtitle {{
    color: #6B7280;
    font-size: 0.95rem;
    margin: 0.25rem 0 0 0;
    font-weight: 400;
}}
.fe-chip {{
    display: inline-block;
    background: #F0F7FF;
    color: {COLOR_PRIMARY};
    border: 1px solid #DBEAFE;
    border-radius: 999px;
    padding: 0.15rem 0.6rem;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    vertical-align: middle;
    margin-left: 0.5rem;
}}
.fe-header-stripe {{
    display: flex;
    gap: 4px;
    margin-bottom: 1rem;
}}
.fe-stripe {{height: 4px; flex: 1; border-radius: 2px;}}
.fe-stripe-blue {{background: {COLOR_PRIMARY};}}
.fe-stripe-cyan {{background: {COLOR_ACCENT};}}
.fe-stripe-green {{background: {COLOR_GREEN};}}
.fe-stripe-yellow {{background: {COLOR_YELLOW};}}
.fe-stripe-orange {{background: {COLOR_ORANGE};}}

/* Status na sidebar */
.fe-status-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.4rem 0;
    border-bottom: 1px solid #E5E7EB;
    font-size: 0.825rem;
}}
.fe-status-row:last-child {{border-bottom: none;}}
.fe-status-label {{color: #4B5563;}}
.fe-status-value {{font-weight: 600;}}
.fe-status-ok {{color: #16A34A;}}
.fe-status-fail {{color: #DC2626;}}
.fe-dot {{
    display: inline-block;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    margin-right: 0.4rem;
    vertical-align: middle;
}}
.fe-dot-ok {{background-color: #16A34A; box-shadow: 0 0 0 3px rgba(22,163,74,0.15);}}
.fe-dot-fail {{background-color: #DC2626; box-shadow: 0 0 0 3px rgba(220,38,38,0.15);}}

/* Botoes de exemplo (cards) */
[data-testid="stSidebar"] .stButton > button {{
    width: 100%;
    text-align: left;
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
    color: #1F2937;
    font-size: 0.825rem;
    font-weight: 500;
    line-height: 1.35;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    transition: all 0.15s ease;
    margin-bottom: 0.4rem;
    white-space: normal;
    height: auto;
    min-height: 2.5rem;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    border-color: {COLOR_PRIMARY};
    background: #F0F7FF;
    color: {COLOR_PRIMARY};
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(26,111,168,0.10);
}}
[data-testid="stSidebar"] .stButton > button:active {{
    transform: translateY(0);
}}

/* Hero de boas-vindas */
.fe-welcome {{
    background: linear-gradient(135deg, #F0F7FF 0%, #FFFFFF 100%);
    border: 1px solid #DBEAFE;
    border-radius: 16px;
    padding: 2.5rem 2rem;
    margin: 1.5rem 0;
    text-align: center;
}}
.fe-welcome-icon {{
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
    line-height: 1;
}}
.fe-welcome-title {{
    font-size: 1.4rem;
    font-weight: 600;
    color: {COLOR_PRIMARY};
    margin: 0 0 0.5rem 0;
    line-height: 1.2;
}}
.fe-welcome-text {{
    color: #4B5563;
    font-size: 0.95rem;
    line-height: 1.6;
    max-width: 580px;
    margin: 0 auto;
}}

/* Footer da sidebar */
.fe-footer {{
    border-top: 1px solid #E5E7EB;
    margin-top: 1.5rem;
    padding-top: 1rem;
    color: #9CA3AF;
    font-size: 0.7rem;
    text-align: center;
    line-height: 1.5;
}}
.fe-footer strong {{color: #6B7280; font-weight: 600;}}

/* Metadata abaixo da resposta */
.fe-meta {{
    color: #9CA3AF;
    font-size: 0.75rem;
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px dashed #E5E7EB;
}}
.fe-meta code {{
    background: #F3F4F6;
    color: #4B5563;
    padding: 0.05rem 0.35rem;
    border-radius: 4px;
    font-size: 0.7rem;
}}

/* Chat input */
[data-testid="stChatInput"] {{border-radius: 12px;}}

/* Mensagens chat */
[data-testid="stChatMessage"] {{
    border-radius: 12px;
    padding: 1rem 1.25rem;
}}
</style>
""",
    unsafe_allow_html=True,
)

# ===== Faixa colorida no topo (paleta IGES) =====
st.markdown(
    """
<div class="fe-header-stripe">
    <div class="fe-stripe fe-stripe-blue"></div>
    <div class="fe-stripe fe-stripe-green"></div>
    <div class="fe-stripe fe-stripe-yellow"></div>
    <div class="fe-stripe fe-stripe-orange"></div>
    <div class="fe-stripe fe-stripe-cyan"></div>
</div>
""",
    unsafe_allow_html=True,
)

# ===== Cabecalho =====
st.markdown(
    """
<div class="fe-header">
    <div class="fe-header-text">
        <h1 class="fe-title">Vagas SISREG DF <span class="fe-chip">POC</span></h1>
        <p class="fe-subtitle">Painel analítico da oferta/capacidade de vagas &nbsp;·&nbsp; SISREG-DF · IGES</p>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ===== Sidebar =====
with st.sidebar:
    st.markdown("### Status do sistema")
    try:
        h = httpx.get(f"{API_BASE_URL}/health", timeout=5, auth=_AUTH).json()
        backend_ok = h.get("ok", False)
        rows = [
            ("Backend", backend_ok),
            ("Fonte de vagas", h.get("fonte_reachable")),
            ("Serviço de IA", h.get("openai_reachable")),
        ]
        for label, is_ok in rows:
            cls = "ok" if is_ok else "fail"
            text = "Operacional" if is_ok else "Indisponível"
            st.markdown(
                f'<div class="fe-status-row">'
                f'<span class="fe-status-label"><span class="fe-dot fe-dot-{cls}"></span>{label}</span>'
                f'<span class="fe-status-value fe-status-{cls}">{text}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        modo = h.get("app_mode", "?")
        expira = h.get("poc_expires_at", "")
        if modo == "poc" and expira:
            st.markdown(
                f'<div class="fe-status-row" style="margin-top:0.5rem;">'
                f'<span class="fe-status-label">Modo POC válido até</span>'
                f'<span class="fe-status-value" style="color:{COLOR_PRIMARY};">{expira}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
    except Exception as exc:
        st.markdown(
            f'<div class="fe-status-row">'
            f'<span class="fe-status-label"><span class="fe-dot fe-dot-fail"></span>Backend</span>'
            f'<span class="fe-status-value fe-status-fail">Indisponivel</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"Detalhe: {type(exc).__name__}")

    st.markdown("### Perguntas frequentes")
    examples = [
        ("Procedimentos com mais vagas", "Quais procedimentos têm mais vagas disponíveis neste mês?"),
        ("Hospitais com mais vagas", "Quais hospitais oferecem mais vagas em julho de 2026?"),
        ("Capacidade bloqueada", "Quanto da capacidade de vagas está bloqueada neste mês?"),
        ("Evolução da oferta", "Como evoluiu a oferta de ressonância magnética ao longo dos meses?"),
        ("Mix por tipo de vaga", "Qual a distribuição das vagas ativas por tipo (1ª vez, retorno, reserva)?"),
        ("Vagas no HUB", "Quantas vagas disponíveis há no Hospital Universitário de Brasília?"),
    ]
    for label, question in examples:
        if st.button(label, key=f"ex-{hash(label)}", use_container_width=True):
            st.session_state["pending_question"] = question
            st.rerun()

    st.markdown(
        f'<div class="fe-footer">'
        f"<strong>IGES-DF</strong> &middot; ZELLO<br>"
        f"v0.1 POC &middot; {date.today().isoformat()}"
        f"</div>",
        unsafe_allow_html=True,
    )

# ===== Estado =====
if "history" not in st.session_state:
    st.session_state.history = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ===== Hero quando nao ha historico =====
if not st.session_state.history:
    st.markdown(
        """
<div class="fe-welcome">
    <div class="fe-welcome-icon">💬</div>
    <h2 class="fe-welcome-title">Como posso ajudar?</h2>
    <p class="fe-welcome-text">
        Faça perguntas em português sobre a <strong>oferta de vagas do SISREG-DF</strong>:
        capacidade por procedimento e hospital, vagas bloqueadas, mix por tipo e tendência.
        Use os exemplos à esquerda ou digite sua pergunta no campo abaixo.
        <br><small>Esta fonte cobre a <em>oferta</em> de vagas, não o tempo de espera da fila.</small>
    </p>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_meta(prov: dict, elapsed: float | None = None) -> None:
    """Linha de metadata discreta abaixo da resposta."""
    bits = []
    if elapsed is not None:
        bits.append(f"<code>{elapsed:.1f}s</code>")
    if prov.get("template"):
        bits.append(f"consulta <code>{prov['template']}</code>")
    if prov.get("indice"):
        bits.append(f"fonte <code>{prov['indice'].replace('-df-brasilia', '')}</code>")
    if bits:
        st.markdown(f'<div class="fe-meta">{" &middot; ".join(bits)}</div>', unsafe_allow_html=True)


def _render_chart_or_scalar(resposta: dict) -> None:
    """Renderiza grafico Plotly se shape!=scalar, ou st.metric se shape=scalar."""
    chart = resposta.get("chart")
    dados = resposta.get("dados") or {}
    if chart:
        st.plotly_chart(chart, use_container_width=True)
        return
    # Scalar -> metric card
    if dados.get("shape") == "scalar" and dados.get("data"):
        prov = resposta.get("proveniencia", {}) or {}
        metric = prov.get("metric", "Resultado")
        units = dados.get("units", "")
        try:
            value = dados["data"][0].get("value")
            if isinstance(value, (int, float)):
                formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if units == "%" else f"{int(value):,}".replace(",", ".")
            else:
                formatted = str(value)
        except Exception:
            formatted = "—"
        label_suffix = f" ({units})" if units and units != "documentos" else ""
        st.metric(label=f"{metric}{label_suffix}", value=formatted)


def _render_details(resposta: dict) -> None:
    """Expansores tecnicos discretos (proveniencia + dados crus)."""
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("Detalhes da consulta"):
            st.json(resposta.get("proveniencia", {}), expanded=False)
    with col2:
        if resposta.get("dados"):
            with st.expander("Dados completos"):
                st.json(resposta["dados"], expanded=False)


# ===== Renderiza historico =====
for entry in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(entry["pergunta"])
    with st.chat_message("assistant"):
        st.markdown(entry["resposta"]["narrativa"])
        _render_chart_or_scalar(entry["resposta"])
        _render_meta(entry["resposta"].get("proveniencia", {}))
        _render_details(entry["resposta"])

# ===== Input =====
pergunta = st.chat_input("Pergunte sobre a fila eletiva…")
if pergunta is None and st.session_state.pending_question:
    pergunta = st.session_state.pending_question
    st.session_state.pending_question = None

if pergunta:
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        with st.spinner("Analisando dados da fila…"):
            try:
                t0 = time.time()
                response = httpx.post(
                    f"{API_BASE_URL}/chat",
                    json={"pergunta": pergunta},
                    timeout=120,
                    auth=_AUTH,
                ).json()
                elapsed = time.time() - t0
                st.markdown(response["narrativa"])
                _render_chart_or_scalar(response)
                _render_meta(response.get("proveniencia", {}), elapsed=elapsed)
                _render_details(response)
                st.session_state.history.append({"pergunta": pergunta, "resposta": response})
            except httpx.ReadTimeout:
                st.error("Tempo limite excedido — a consulta levou mais de 2 minutos.")
            except Exception as exc:
                st.error(f"Erro ao consultar a API: {exc}")
