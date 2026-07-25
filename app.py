"""
app.py
Ponto de entrada do sistema. Faz a autenticação, monta o menu lateral de
acordo com o PERFIL do usuário logado e roteia para o módulo certo.

Como rodar:
    streamlit run app.py

Perfis e o que cada um vê no menu:
    admin_geral -> Gestão de Assinantes + acesso completo (para suporte)
    dono        -> tudo: PDV, Estoque, Compras, Fiado, Financeiro, Dashboard, Equipe
    gerente     -> igual ao dono (exceto Gestão de Assinantes)
    operador    -> apenas PDV e Fiado (Clientes); histórico de caixa restrito
                   aos próprios caixas, sem ver diferença/expectativa de gaveta
"""
import streamlit as st

import config  # noqa: F401  (aplica page_config + CSS ao ser importado)
from auth import inicializar_sessao, tela_login_e_cadastro, fazer_logout, tem_acesso_completo
from caixa import buscar_caixa_aberto, tela_abrir_caixa, tela_historico_caixas
from pdv import tela_pdv
from fiado import tela_fiado
from estoque import tela_estoque
from compras import tela_compras
from financeiro import tela_financeiro
from dashboard import tela_dashboard
from admin import tela_gestao_assinantes
from equipe import tela_equipe

# ==============================================================
# 1. SESSÃO / LOGIN
# ==============================================================
inicializar_sessao()

if not st.session_state['logado']:
    tela_login_e_cadastro()

# ==============================================================
# 2. ÁREA LOGADA — SIDEBAR
# ==============================================================
nome_usuario = st.session_state['nome_usuario']
perfil = st.session_state['perfil']

st.sidebar.markdown(f"### 👋 Olá, {nome_usuario}")
st.sidebar.caption(f"Perfil: {perfil.capitalize()}")
st.sidebar.button("Sair / Desconectar", on_click=fazer_logout)
st.sidebar.markdown("---")

# ---- Menu segmentado por perfil ----
if perfil == "operador":
    opcoes_menu = ["🧾 PDV", "💳 Fiado (Clientes)"]
elif perfil == "admin_geral":
    opcoes_menu = ["👑 Gestão de Assinantes", "🧾 PDV", "📦 Estoque", "🛒 Compras",
                   "💳 Fiado (Clientes)", "💰 Financeiro", "📊 Dashboard", "👥 Equipe"]
else:  # dono, gerente
    opcoes_menu = ["📊 Dashboard", "🧾 PDV", "📦 Estoque", "🛒 Compras",
                   "💳 Fiado (Clientes)", "💰 Financeiro", "👥 Equipe"]

menu = st.sidebar.radio("Módulos", opcoes_menu)

# ==============================================================
# 3. ROTEAMENTO
# ==============================================================
if menu == "👑 Gestão de Assinantes":
    tela_gestao_assinantes()

elif menu == "🧾 PDV":
    if tem_acesso_completo():
        tab_venda, tab_historico = st.tabs(["🧾 Venda", "📜 Histórico de Caixas"])
        with tab_venda:
            caixa_atual = buscar_caixa_aberto()
            if not caixa_atual:
                tela_abrir_caixa()
            else:
                tela_pdv(caixa_atual)
        with tab_historico:
            tela_historico_caixas()
    else:
        # Operador: mesma experiência, mas o histórico já vem filtrado e "cego"
        # dentro de tela_historico_caixas / widget_status_caixa.
        tab_venda, tab_historico = st.tabs(["🧾 Venda", "📜 Meus Caixas"])
        with tab_venda:
            caixa_atual = buscar_caixa_aberto()
            if not caixa_atual:
                tela_abrir_caixa()
            else:
                tela_pdv(caixa_atual)
        with tab_historico:
            tela_historico_caixas()

elif menu == "📦 Estoque":
    tela_estoque()

elif menu == "🛒 Compras":
    tela_compras()

elif menu == "💳 Fiado (Clientes)":
    tela_fiado()

elif menu == "💰 Financeiro":
    tela_financeiro()

elif menu == "📊 Dashboard":
    tela_dashboard()

elif menu == "👥 Equipe":
    tela_equipe()
