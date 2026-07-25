"""
config.py
Configuração geral do sistema: conexão com o Supabase, configuração da página
e estilo visual (CSS). Importado por app.py antes de qualquer outro módulo.
"""
import streamlit as st
from supabase import create_client, Client

# ==============================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================
st.set_page_config(page_title="Mercadinho - Sistema", page_icon="🛒", layout="wide")

# ==============================================================
# FORÇA TÍTULO E FAVICON DA ABA (contorna limitação do Streamlit
# Community Cloud, que às vezes ignora o page_title/page_icon
# acima e mantém "Streamlit" + logo padrão na aba do navegador)
# ==============================================================
import streamlit.components.v1 as _components

_components.html("""
<script>
try {
    var doc = window.parent.document;
    doc.title = "Mercadinho - Sistema";

    var favicon = doc.querySelector("link[rel~='icon']");
    if (!favicon) {
        favicon = doc.createElement('link');
        favicon.rel = 'icon';
        doc.head.appendChild(favicon);
    }
    favicon.href = "https://raw.githubusercontent.com/valdemirnn/valdemirmercadinho/main/logo_sem_fundo.png";

    // Reaplica a cada 1s por alguns segundos, caso o Streamlit sobrescreva de volta
    var tentativas = 0;
    var intervalo = setInterval(function() {
        doc.title = "Mercadinho - Sistema";
        favicon.href = "https://raw.githubusercontent.com/valdemirnn/valdemirmercadinho/main/logo_sem_fundo.png";
        tentativas++;
        if (tentativas > 10) clearInterval(intervalo);
    }, 1000);
} catch (e) {}
</script>
""", height=0, width=0)

# ==============================================================
# CUSTOMIZAÇÃO VISUAL (CSS)
# ==============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ---- Título principal com barrinha azul à esquerda ---- */
h1 {
    font-weight: 800 !important;
    font-size: 2.4rem !important;
    padding-left: 16px;
    border-left: 6px solid #3B82F6;
}
h2, h3 { font-weight: 700 !important; }

/* ---- Botões ---- */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button, .stLinkButton > a {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 1.05rem !important;
    padding: 0.6rem 1rem !important;
    transition: all 0.15s ease-in-out;
    border: 1px solid #3B82F6 !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background-color: #3B82F6 !important;
    color: white !important;
    box-shadow: 0 2px 10px rgba(59,130,246,0.45);
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(59,130,246,0.35);
}

/* ---- Cartões de métrica (KPIs) ---- */
div[data-testid="stMetric"] {
    background-color: #1B2438;
    border: 1px solid #2A3752;
    border-top: 4px solid #3B82F6;
    border-radius: 12px;
    padding: 16px 18px 12px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
div[data-testid="stMetricLabel"] { font-weight: 600 !important; }
div[data-testid="stMetricValue"] { color: #7CB2FF !important; font-size: 1.7rem !important; }

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background-color: #131B2C;
    border-right: 1px solid #2A3752;
}
section[data-testid="stSidebar"] .stRadio label {
    font-weight: 600;
    font-size: 1.05rem;
}

/* ---- Abas (tabs) ---- */
.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    font-size: 1.02rem;
    border-radius: 8px 8px 0 0;
}
.stTabs [aria-selected="true"] {
    color: #7CB2FF !important;
    border-bottom: 3px solid #3B82F6 !important;
}

/* ---- Expanders (cards de produto/cliente/pedido) ---- */
div[data-testid="stExpander"] {
    background-color: #161F33 !important;
    border: 1px solid #2A3752 !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
div[data-testid="stExpander"] summary {
    font-weight: 600;
    font-size: 1.02rem;
}

/* ---- Inputs ---- */
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input,
div[data-baseweb="select"], div[data-baseweb="input"] {
    border-radius: 8px !important;
    font-size: 1.05rem !important;
}
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input {
    padding: 0.6rem 0.8rem !important;
}

/* ---- Cartão de Login, bem maior e centralizado ---- */
div[data-testid="stForm"] {
    background-color: #161F33;
    border: 1px solid #2A3752;
    border-radius: 18px;
    padding: 40px 46px 26px 46px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.35);
    width: 100%;
}
div[data-testid="stForm"] label {
    font-size: 1.1rem !important;
}

/* Oculta a mensagem "Press Enter to submit form" */
div[data-testid="InputInstructions"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================
# SEGREDOS / VARIÁVEIS DE CONFIGURAÇÃO
# ==============================================================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

GMAIL_REMETENTE = st.secrets.get("GMAIL_REMETENTE", "")
GMAIL_SENHA_APP = st.secrets.get("GMAIL_SENHA_APP", "")
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN", "")
URL_BASE_SISTEMA = st.secrets.get("URL_BASE_SISTEMA", "http://localhost:8501")
VALOR_ASSINATURA_MENSAL = float(st.secrets.get("VALOR_ASSINATURA_MENSAL", 100.00))

SECRET_TOKEN_KEY = "mercadinho_sistema_2026_chave_secreta"

# ==============================================================
# CONEXÃO COM O SUPABASE (client único, reaproveitado)
# ==============================================================
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = init_connection()
except Exception:
    st.error("Erro ao conectar com o banco. Verifique SUPABASE_URL e SUPABASE_KEY nos secrets.")
    st.stop()
