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
from auth import (
    inicializar_sessao, tela_login_e_cadastro, fazer_logout, tem_acesso_completo,
    MODULOS_EXTRAS_DISPONIVEIS
)
from caixa import buscar_caixa_aberto, tela_abrir_caixa, tela_historico_caixas
from pdv import tela_pdv
from fiado import tela_fiado
from estoque import tela_estoque
from compras import tela_compras
from financeiro import tela_financeiro
from dashboard import tela_dashboard
from admin import tela_gestao_assinantes
from equipe import tela_equipe
from perfil import tela_meu_perfil

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
cargo = st.session_state.get('cargo') or perfil.capitalize()
foto_base64_usuario = st.session_state.get('foto_base64')

if foto_base64_usuario:
    avatar_html = f"""<img src="data:image/jpeg;base64,{foto_base64_usuario}"
        style="width:64px;height:64px;border-radius:50%;object-fit:cover;border:2px solid #3B82F6;" />"""
else:
    avatar_html = """<div style="width:64px;height:64px;border-radius:50%;background-color:#5F6368;
        display:flex;align-items:center;justify-content:center;border:2px solid #3B82F6;">
        <svg viewBox="0 0 24 24" width="36" height="36" fill="white">
            <circle cx="12" cy="8" r="4"/>
            <path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6v1H4v-1z"/>
        </svg>
    </div>"""

st.sidebar.markdown(avatar_html, unsafe_allow_html=True)
st.sidebar.markdown(f"### 👋 Olá, {nome_usuario}")
st.sidebar.caption(f"Cargo: {cargo}")
if st.sidebar.button("👤 Meu Perfil", use_container_width=True):
    st.session_state['ver_meu_perfil'] = True
    st.rerun()
st.sidebar.button("Sair / Desconectar", on_click=fazer_logout)
st.sidebar.markdown("---")

if st.session_state.get('ver_meu_perfil'):
    if st.button("⬅️ Voltar"):
        st.session_state['ver_meu_perfil'] = False
        st.rerun()
    tela_meu_perfil()
    st.stop()

# ---- Menu segmentado por perfil ----
if perfil == "operador":
    permissoes_extras_usuario = st.session_state.get('permissoes_extras') or []
    opcoes_menu = ["🧾 PDV"]
    for chave_modulo, label_modulo in MODULOS_EXTRAS_DISPONIVEIS:
        if chave_modulo in permissoes_extras_usuario:
            opcoes_menu.append(label_modulo)
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
