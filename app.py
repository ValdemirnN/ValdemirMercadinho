import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import hashlib
import io
import smtplib
from email.mime.text import MIMEText
import requests
import secrets

# ==============================================================
# 1. CONFIGURAÇÃO E CONEXÃO
# ==============================================================
st.set_page_config(page_title="Mercadinho - Sistema", page_icon="🛒", layout="wide")

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

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

# ==============================================================
# CONFIGURAÇÕES DE E-MAIL E PAGAMENTO (assinatura do sistema)
# ==============================================================
GMAIL_REMETENTE = st.secrets.get("GMAIL_REMETENTE", "")
GMAIL_SENHA_APP = st.secrets.get("GMAIL_SENHA_APP", "")
MP_ACCESS_TOKEN = st.secrets.get("MP_ACCESS_TOKEN", "")
URL_BASE_SISTEMA = st.secrets.get("URL_BASE_SISTEMA", "http://localhost:8501")
VALOR_ASSINATURA_MENSAL = float(st.secrets.get("VALOR_ASSINATURA_MENSAL", 100.00))

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Erro ao conectar com o banco. Verifique SUPABASE_URL e SUPABASE_KEY nos secrets.")
    st.stop()

# ==============================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================
def formatar_moeda(valor):
    if valor is None:
        return "0,00"
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def mostrar_popup(mensagem, tipo="sucesso"):
    if tipo == "erro":
        st.error(f"⚠️ {mensagem}")
    else:
        st.success(f"✅ {mensagem}")

SECRET_TOKEN_KEY = "mercadinho_sistema_2026_chave_secreta"

def gerar_token_sessao(usuario_id, senha_hash):
    base = f"{usuario_id}:{senha_hash}:{SECRET_TOKEN_KEY}"
    return hashlib.sha256(base.encode()).hexdigest()[:24]

# ==============================================================
# ASSINATURA: E-MAIL DE CONFIRMAÇÃO
# ==============================================================
def enviar_email_confirmacao(destinatario, nome_destinatario, token):
    link_confirmacao = f"{URL_BASE_SISTEMA}/?confirmar_email={token}"
    corpo = (
        f"Olá {nome_destinatario},\n\n"
        f"Obrigado por criar sua conta no Sistema Mercadinho!\n"
        f"Para confirmar seu e-mail e prosseguir com a ativação, clique no link abaixo:\n{link_confirmacao}\n"
    )
    msg = MIMEText(corpo)
    msg['Subject'] = "Confirme seu e-mail - Sistema Mercadinho"
    msg['From'] = GMAIL_REMETENTE
    msg['To'] = destinatario
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as servidor:
            servidor.login(GMAIL_REMETENTE, GMAIL_SENHA_APP)
            servidor.sendmail(GMAIL_REMETENTE, destinatario, msg.as_string())
        return True
    except Exception as e:
        st.error(f"⚠️ Conta criada, mas houve erro ao enviar o e-mail de confirmação ({e}).")
        return False

def confirmar_email_por_link():
    try:
        token_param = st.query_params.get("confirmar_email")
        if token_param:
            resultado = supabase.table("usuarios").select("id, email, nome").eq("token_confirmacao", token_param).execute()
            if resultado.data:
                usuario_confirmado = resultado.data[0]
                supabase.table("usuarios").update({
                    "email_confirmado": True, "token_confirmacao": None
                }).eq("id", usuario_confirmado['id']).execute()
                st.session_state.update({
                    'conta_criada_id': usuario_confirmado['id'],
                    'conta_criada_email': usuario_confirmado['email'],
                    'conta_criada_nome': usuario_confirmado.get('nome') or usuario_confirmado['email']
                })
            else:
                st.session_state['erro_confirmacao_msg'] = "Link de confirmação inválido ou já utilizado."
            st.query_params.clear()
    except Exception:
        pass

# ==============================================================
# ASSINATURA: MERCADO PAGO
# ==============================================================
def criar_preferencia_pagamento_mp(usuario_id, email_cliente, descricao, valor):
    url = "https://api.mercadopago.com/checkout/preferences"
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "items": [{"title": descricao, "quantity": 1, "unit_price": float(valor), "currency_id": "BRL"}],
        "payer": {"email": email_cliente},
        "external_reference": str(usuario_id),
        "back_urls": {"success": URL_BASE_SISTEMA, "failure": URL_BASE_SISTEMA, "pending": URL_BASE_SISTEMA}
    }
    resposta = requests.post(url, json=payload, headers=headers, timeout=15)
    resposta.raise_for_status()
    return resposta.json()

def verificar_pagamento_mp(usuario_id):
    url = "https://api.mercadopago.com/v1/payments/search"
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
    params = {"external_reference": str(usuario_id)}
    resposta = requests.get(url, headers=headers, params=params, timeout=15)
    resposta.raise_for_status()
    for pagamento in resposta.json().get("results", []):
        if pagamento.get("status") == "approved":
            return True
    return False

def ativar_conta_apos_pagamento(usuario_id, metodo):
    novo_vencimento = datetime.now() + relativedelta(months=1)
    resultado_user = supabase.table("usuarios").select("empresa_id").eq("id", usuario_id).execute()
    if resultado_user.data:
        empresa_id_pag = resultado_user.data[0]['empresa_id']
        supabase.table("assinaturas").update({
            "data_vencimento": novo_vencimento.strftime("%Y-%m-%d")
        }).eq("empresa_id", empresa_id_pag).execute()
    supabase.table("usuarios").update({"ativo": True, "metodo_pagamento": metodo}).eq("id", usuario_id).execute()

def verificar_assinatura_valida(empresa_id_check):
    """Retorna True se a assinatura da empresa está em dia (ou não encontrada = trata como válida)."""
    assinatura_check = supabase.table("assinaturas").select("data_vencimento") \
        .eq("empresa_id", empresa_id_check).order("data_vencimento", desc=True).limit(1).execute()
    if not assinatura_check.data:
        return True
    try:
        venc = datetime.strptime(assinatura_check.data[0]['data_vencimento'], "%Y-%m-%d").date()
        return venc >= date.today()
    except Exception:
        return True

def restaurar_sessao_por_token():
    try:
        params = st.query_params
        uid_param = params.get("uid")
        tk_param = params.get("tk")
        if uid_param and tk_param:
            usuario_id_restaurar = int(uid_param)
            resultado = supabase.table("usuarios").select(
                "id, nome, senha_hash, perfil, empresa_id, ativo"
            ).eq("id", usuario_id_restaurar).execute()
            if resultado.data:
                usuario = resultado.data[0]
                token_esperado = gerar_token_sessao(usuario['id'], usuario['senha_hash'])
                if usuario['ativo'] and tk_param == token_esperado:
                    assinatura_ok = usuario['perfil'] == 'admin_geral' or verificar_assinatura_valida(usuario['empresa_id'])
                    if assinatura_ok:
                        st.session_state.update({
                            'logado': True,
                            'perfil': usuario['perfil'],
                            'empresa_id': usuario['empresa_id'],
                            'usuario_id': usuario['id'],
                            'nome_usuario': usuario['nome']
                        })
                    else:
                        st.query_params.clear()
    except Exception:
        pass

def fazer_logout():
    st.session_state.update({
        'logado': False, 'perfil': '', 'empresa_id': None,
        'usuario_id': None, 'nome_usuario': ''
    })
    st.query_params.clear()

if 'logado' not in st.session_state:
    st.session_state.update({
        'logado': False, 'perfil': '', 'empresa_id': None,
        'usuario_id': None, 'nome_usuario': ''
    })
    restaurar_sessao_por_token()

if st.query_params.get("confirmar_email"):
    confirmar_email_por_link()

# ==============================================================
# 3. TELA DE LOGIN / CADASTRO / PAGAMENTO
# ==============================================================
if not st.session_state['logado']:

    # ----------------------------------------------------------
    # ETAPA DE PAGAMENTO (depois que o e-mail foi confirmado)
    # ----------------------------------------------------------
    if st.session_state.get('conta_criada_id'):
        st.write("")
        col_pag1, col_pag2, col_pag3 = st.columns([1, 1.6, 1])
        with col_pag2:
            st.title("💳 Finalizar Assinatura")
            st.success(f"E-mail confirmado, {st.session_state.get('conta_criada_nome', '')}! Falta só ativar sua conta.")

            st.info(f"📦 **Assinatura Mensal — R$ {formatar_moeda(VALOR_ASSINATURA_MENSAL)}/mês**\n\nAcesso completo: PDV, Estoque, Fiado, Compras, Financeiro e Dashboard.")

            metodo_escolhido = st.radio("Como quer pagar?", ["📱 Pix", "💳 Cartão de Crédito", "🤝 Pagar em mãos"])

            if metodo_escolhido.startswith("🤝"):
                comprovante_pagamento = st.text_area("Descreva como/quando foi combinado o pagamento")
                if st.button("📤 Enviar para aprovação"):
                    if not comprovante_pagamento.strip():
                        mostrar_popup("Descreva o combinado do pagamento.", tipo="erro")
                    else:
                        supabase.table("usuarios").update({
                            "metodo_pagamento": "manual", "comprovante_pagamento": comprovante_pagamento
                        }).eq("id", st.session_state['conta_criada_id']).execute()
                        mostrar_popup("Enviado! Assim que o pagamento for confirmado, sua conta será liberada.")
                        del st.session_state['conta_criada_id']
                        st.rerun()
            else:
                if st.button("Gerar Link de Pagamento"):
                    try:
                        preferencia = criar_preferencia_pagamento_mp(
                            st.session_state['conta_criada_id'], st.session_state['conta_criada_email'],
                            "Assinatura Mensal - Sistema Mercadinho", VALOR_ASSINATURA_MENSAL
                        )
                        st.session_state['link_pagamento_mp'] = preferencia.get('init_point')
                        supabase.table("usuarios").update({
                            "metodo_pagamento": "pix" if "Pix" in metodo_escolhido else "cartao"
                        }).eq("id", st.session_state['conta_criada_id']).execute()
                    except Exception as e:
                        mostrar_popup(f"Erro ao gerar link: {e}", tipo="erro")

                if st.session_state.get('link_pagamento_mp'):
                    st.link_button("🔗 Ir para Pagamento", st.session_state['link_pagamento_mp'], use_container_width=True)
                    if st.button("🔄 Já paguei, verificar", use_container_width=True):
                        if verificar_pagamento_mp(st.session_state['conta_criada_id']):
                            ativar_conta_apos_pagamento(st.session_state['conta_criada_id'], "pix")
                            mostrar_popup("Pagamento confirmado! Sua conta já está ativa. Faça login.")
                            del st.session_state['conta_criada_id']
                            if 'link_pagamento_mp' in st.session_state:
                                del st.session_state['link_pagamento_mp']
                            st.rerun()
                        else:
                            mostrar_popup("Pagamento não identificado ainda. Pode levar alguns minutos.", tipo="erro")
        st.stop()

    # ----------------------------------------------------------
    # HERO + LOGIN (split-screen)
    # ----------------------------------------------------------
    if st.session_state.get('erro_confirmacao_msg'):
        st.error(f"⚠️ {st.session_state['erro_confirmacao_msg']}")
        del st.session_state['erro_confirmacao_msg']

    st.write("")
    col_hero, col_form = st.columns([1.15, 1])

    with col_hero:
        st.write("")
        st.markdown("# 🛒 Sistema Mercadinho")
        st.markdown("#### Gestão completa para o seu mercadinho, num só lugar.")
        st.write("")
        st.markdown("✅ **PDV rápido** — código de barras ou busca por nome")
        st.markdown("✅ **Controle de estoque** — alertas de estoque baixo e validade")
        st.markdown("✅ **Fiado organizado** — saldo por cliente, sem anotar em caderno")
        st.markdown("✅ **Compras e fornecedores** — saiba o que está chegando")
        st.markdown("✅ **Financeiro e Dashboard** — veja o lucro de verdade")

    with col_form:
        st.title("🔐 Login")
        st.caption("Acesse sua conta")
        st.write("")

        with st.form("form_login"):
            email_login = st.text_input("E-mail")
            senha_login = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if entrar:
            try:
                resultado = supabase.table("usuarios").select(
                    "id, nome, senha_hash, perfil, empresa_id, ativo"
                ).eq("email", email_login).execute()

                if resultado.data:
                    usuario = resultado.data[0]
                    if not usuario['ativo']:
                        mostrar_popup("Usuário bloqueado ou aguardando confirmação de pagamento.", tipo="erro")
                    elif usuario['senha_hash'] == senha_login:
                        assinatura_ok = usuario['perfil'] == 'admin_geral' or verificar_assinatura_valida(usuario['empresa_id'])
                        if not assinatura_ok:
                            mostrar_popup("Assinatura vencida. Entre em contato para renovar o acesso.", tipo="erro")
                        else:
                            st.session_state.update({
                                'logado': True,
                                'perfil': usuario['perfil'],
                                'empresa_id': usuario['empresa_id'],
                                'usuario_id': usuario['id'],
                                'nome_usuario': usuario['nome']
                            })
                            st.query_params.update({
                                "uid": str(usuario['id']),
                                "tk": gerar_token_sessao(usuario['id'], usuario['senha_hash'])
                            })
                            st.rerun()
                    else:
                        mostrar_popup("Senha incorreta.", tipo="erro")
                else:
                    mostrar_popup("E-mail não encontrado.", tipo="erro")
            except Exception as e:
                mostrar_popup(f"Erro ao tentar logar: {e}", tipo="erro")

        st.markdown("---")
        with st.expander("🆕 Ainda não tem conta? Criar conta"):
            with st.form("form_criar_conta"):
                nome_empresa_cadastro = st.text_input("Nome do Mercadinho")
                nome_usuario_cadastro = st.text_input("Seu Nome")
                email_cadastro = st.text_input("E-mail")
                senha_cadastro = st.text_input("Senha", type="password")
                senha_cadastro_confirma = st.text_input("Confirme a Senha", type="password")
                criar_conta_btn = st.form_submit_button("Criar Conta", use_container_width=True)

            if criar_conta_btn:
                if not nome_empresa_cadastro.strip() or not nome_usuario_cadastro.strip() or not email_cadastro.strip():
                    mostrar_popup("Preencha todos os campos.", tipo="erro")
                elif senha_cadastro != senha_cadastro_confirma:
                    mostrar_popup("As senhas não coincidem.", tipo="erro")
                elif len(senha_cadastro) < 7:
                    mostrar_popup("A senha precisa ter no mínimo 7 caracteres.", tipo="erro")
                else:
                    try:
                        email_existente = supabase.table("usuarios").select("id").eq("email", email_cadastro).execute()
                    except Exception as e_check:
                        email_existente = None
                        mostrar_popup(f"Erro ao consultar e-mail: {e_check}", tipo="erro")

                    if email_existente and email_existente.data:
                        mostrar_popup("Já existe uma conta com esse e-mail.", tipo="erro")
                    elif email_existente is not None:
                        try:
                            plano_padrao = supabase.table("planos").select("id").order("id").limit(1).execute()
                        except Exception as e_plano:
                            plano_padrao = None
                            mostrar_popup(f"Erro ao consultar planos: {e_plano}", tipo="erro")

                        if plano_padrao is not None and not plano_padrao.data:
                            mostrar_popup("Nenhum plano cadastrado no banco de dados. Rode a migração de assinaturas.", tipo="erro")
                        elif plano_padrao is not None:
                            try:
                                nova_empresa = supabase.table("empresas").insert({"nome_fantasia": nome_empresa_cadastro}).execute()
                                empresa_id_criada = nova_empresa.data[0]['id']
                                hoje_cadastro = datetime.now().strftime("%Y-%m-%d")
                                supabase.table("assinaturas").insert({
                                    "empresa_id": empresa_id_criada, "plano_id": plano_padrao.data[0]['id'],
                                    "data_inicio": hoje_cadastro, "data_vencimento": hoje_cadastro
                                }).execute()
                                token_confirmacao_novo = secrets.token_urlsafe(24)
                                supabase.table("usuarios").insert({
                                    "empresa_id": empresa_id_criada, "nome": nome_usuario_cadastro,
                                    "email": email_cadastro, "senha_hash": senha_cadastro, "perfil": "dono",
                                    "ativo": False, "email_confirmado": False, "token_confirmacao": token_confirmacao_novo
                                }).execute()
                                enviar_email_confirmacao(email_cadastro, nome_usuario_cadastro, token_confirmacao_novo)
                                mostrar_popup("Conta criada! Enviamos um e-mail de confirmação — clique no link para prosseguir com o pagamento.")
                            except Exception as e_criar:
                                mostrar_popup(f"Erro ao criar conta: {e_criar}", tipo="erro")

    st.stop()

# ==============================================================
# 4. ÁREA LOGADA
# ==============================================================
emp_id = st.session_state['empresa_id']
usuario_id = st.session_state['usuario_id']
nome_usuario = st.session_state['nome_usuario']

st.sidebar.markdown(f"### 👋 Olá, {nome_usuario}")
st.sidebar.caption(f"Perfil: {st.session_state['perfil'].capitalize()}")
st.sidebar.button("Sair / Desconectar", on_click=fazer_logout)
st.sidebar.markdown("---")

opcoes_menu = ["🧾 PDV", "📦 Estoque", "🛒 Compras", "💳 Fiado (Clientes)", "💰 Financeiro", "📊 Dashboard"]
if st.session_state['perfil'] == 'admin_geral':
    opcoes_menu = ["👑 Gestão de Assinantes"] + opcoes_menu
menu = st.sidebar.radio("Módulos", opcoes_menu)

# ==============================================================
# 5. CONTROLE DE CAIXA (compartilhado entre módulos)
# ==============================================================
def buscar_caixa_aberto():
    resultado = supabase.table("caixas").select("*").eq("empresa_id", emp_id) \
        .eq("operador_id", usuario_id).eq("status", "aberto").order("id", desc=True).limit(1).execute()
    return resultado.data[0] if resultado.data else None

def tela_abrir_caixa():
    st.title("🔒 Abertura de Caixa")
    st.info("Você precisa abrir o caixa antes de registrar vendas.")
    with st.form("form_abrir_caixa"):
        valor_abertura = st.number_input("Valor inicial na gaveta (troco)", min_value=0.0, step=5.0, value=0.0, format="%.2f")
        abrir = st.form_submit_button("🔓 Abrir Caixa")
    if abrir:
        supabase.table("caixas").insert({
            "empresa_id": emp_id,
            "operador_id": usuario_id,
            "valor_abertura": valor_abertura,
            "status": "aberto"
        }).execute()
        mostrar_popup("CAIXA ABERTO COM SUCESSO!")
        st.rerun()

def calcular_totais_caixa(caixa):
    vendas_caixa = supabase.table("vendas").select("valor_total, forma_pagamento, status") \
        .eq("caixa_id", caixa['id']).eq("status", "concluida").execute()
    total_dinheiro = sum(float(v['valor_total']) for v in (vendas_caixa.data or []) if v['forma_pagamento'] == 'dinheiro')
    total_geral = sum(float(v['valor_total']) for v in (vendas_caixa.data or []))
    qtd_vendas = len(vendas_caixa.data or [])

    sangrias = supabase.table("sangrias_caixa").select("valor").eq("caixa_id", caixa['id']).execute()
    total_sangrias = sum(float(s['valor']) for s in (sangrias.data or []))

    valor_esperado_gaveta = float(caixa['valor_abertura']) + total_dinheiro - total_sangrias
    return {
        "total_dinheiro": total_dinheiro, "total_geral": total_geral, "qtd_vendas": qtd_vendas,
        "total_sangrias": total_sangrias, "valor_esperado_gaveta": valor_esperado_gaveta
    }

def widget_status_caixa(caixa):
    with st.sidebar.expander("💵 Caixa Aberto", expanded=False):
        totais = calcular_totais_caixa(caixa)
        st.write(f"Abertura: R$ {formatar_moeda(caixa['valor_abertura'])}")
        st.write(f"Vendas: {totais['qtd_vendas']} (R$ {formatar_moeda(totais['total_geral'])})")
        st.write(f"Sangrias: R$ {formatar_moeda(totais['total_sangrias'])}")
        st.write(f"**Esperado na gaveta: R$ {formatar_moeda(totais['valor_esperado_gaveta'])}**")

        st.markdown("---")
        st.caption("Registrar sangria (retirada de dinheiro)")
        valor_sangria = st.number_input("Valor", min_value=0.0, step=5.0, format="%.2f", key="valor_sangria_sidebar")
        motivo_sangria = st.text_input("Motivo", key="motivo_sangria_sidebar")
        if st.button("Registrar Sangria", key="btn_sangria_sidebar"):
            if valor_sangria > 0 and motivo_sangria.strip():
                supabase.table("sangrias_caixa").insert({
                    "caixa_id": caixa['id'], "valor": valor_sangria, "motivo": motivo_sangria
                }).execute()
                mostrar_popup("SANGRIA REGISTRADA!")
                st.rerun()
            else:
                mostrar_popup("Informe valor e motivo.", tipo="erro")

        st.markdown("---")
        st.caption("Fechar caixa")
        valor_fechamento_informado = st.number_input("Valor contado na gaveta", min_value=0.0, step=5.0, format="%.2f", key="valor_fechamento_sidebar")
        if st.button("🔒 Fechar Caixa", key="btn_fechar_caixa_sidebar"):
            diferenca = valor_fechamento_informado - totais['valor_esperado_gaveta']
            supabase.table("caixas").update({
                "status": "fechado",
                "valor_fechamento_informado": valor_fechamento_informado,
                "valor_fechamento_calculado": totais['valor_esperado_gaveta'],
                "diferenca": diferenca,
                "data_fechamento": datetime.now().isoformat()
            }).eq("id", caixa['id']).execute()
            if abs(diferenca) < 0.01:
                mostrar_popup("CAIXA FECHADO! Bateu certinho. 🎉")
            elif diferenca > 0:
                mostrar_popup(f"Caixa fechado. Sobrou R$ {formatar_moeda(diferenca)} a mais na gaveta.")
            else:
                mostrar_popup(f"Caixa fechado. Faltou R$ {formatar_moeda(abs(diferenca))} na gaveta.", tipo="erro")
            st.rerun()

# ==============================================================
# 6. MÓDULO PDV
# ==============================================================
def tela_pdv(caixa):
    st.title("🧾 Ponto de Venda")
    widget_status_caixa(caixa)

    if 'carrinho_pdv' not in st.session_state:
        st.session_state['carrinho_pdv'] = []

    produtos_todos = supabase.table("produtos").select(
        "id, nome, codigo_barras, preco_venda, estoque_atual, unidade"
    ).eq("empresa_id", emp_id).eq("ativo", True).execute()
    dict_produtos = {p['id']: p for p in (produtos_todos.data or [])}
    mapa_codigo_barras = {p['codigo_barras']: p for p in (produtos_todos.data or []) if p.get('codigo_barras')}

    col_busca, col_carrinho = st.columns([1, 1.3])

    with col_busca:
        st.subheader("🔍 Adicionar Produto")
        tab_cod, tab_nome = st.tabs(["📷 Código de Barras", "🔤 Buscar por Nome"])

        with tab_cod:
            codigo_digitado = st.text_input("Escaneie ou digite o código de barras", key="input_codigo_barras")
            if codigo_digitado:
                produto_encontrado = mapa_codigo_barras.get(codigo_digitado.strip())
                if produto_encontrado:
                    if produto_encontrado['estoque_atual'] <= 0:
                        st.warning(f"⚠️ {produto_encontrado['nome']} está sem estoque.")
                    else:
                        já_no_carrinho = next((i for i in st.session_state['carrinho_pdv'] if i['produto_id'] == produto_encontrado['id']), None)
                        if já_no_carrinho:
                            já_no_carrinho['quantidade'] += 1
                            já_no_carrinho['subtotal'] = já_no_carrinho['quantidade'] * já_no_carrinho['preco_unitario']
                        else:
                            st.session_state['carrinho_pdv'].append({
                                'produto_id': produto_encontrado['id'], 'nome': produto_encontrado['nome'],
                                'preco_unitario': float(produto_encontrado['preco_venda']),
                                'quantidade': 1, 'subtotal': float(produto_encontrado['preco_venda']),
                                'unidade': produto_encontrado['unidade']
                            })
                        st.rerun()
                else:
                    st.warning("Nenhum produto com esse código de barras.")

        with tab_nome:
            termo_busca = st.text_input("Digite o nome do produto", key="input_busca_nome")
            if termo_busca:
                encontrados = [p for p in (produtos_todos.data or []) if termo_busca.lower() in p['nome'].lower()]
                for p in encontrados[:8]:
                    disp = f"{p['nome']} — R$ {formatar_moeda(p['preco_venda'])} (Estoque: {p['estoque_atual']})"
                    col_p1, col_p2 = st.columns([3, 1])
                    col_p1.write(disp)
                    if col_p2.button("➕ Add", key=f"add_prod_{p['id']}"):
                        if p['estoque_atual'] <= 0:
                            mostrar_popup(f"{p['nome']} está sem estoque.", tipo="erro")
                        else:
                            já_no_carrinho = next((i for i in st.session_state['carrinho_pdv'] if i['produto_id'] == p['id']), None)
                            if já_no_carrinho:
                                já_no_carrinho['quantidade'] += 1
                                já_no_carrinho['subtotal'] = já_no_carrinho['quantidade'] * já_no_carrinho['preco_unitario']
                            else:
                                st.session_state['carrinho_pdv'].append({
                                    'produto_id': p['id'], 'nome': p['nome'],
                                    'preco_unitario': float(p['preco_venda']),
                                    'quantidade': 1, 'subtotal': float(p['preco_venda']),
                                    'unidade': p['unidade']
                                })
                            st.rerun()

    with col_carrinho:
        st.subheader("🛒 Carrinho")
        if not st.session_state['carrinho_pdv']:
            st.info("Carrinho vazio. Busque um produto ao lado.")
        else:
            for idx, item in enumerate(st.session_state['carrinho_pdv']):
                estoque_disp = dict_produtos.get(item['produto_id'], {}).get('estoque_atual', 0)
                c1, c2, c3, c4 = st.columns([3, 1.2, 1.3, 0.6])
                c1.write(f"**{item['nome']}**")
                nova_qtd = c2.number_input("Qtd", min_value=0.0, max_value=float(estoque_disp), value=float(item['quantidade']),
                                            step=1.0, key=f"qtd_carrinho_{idx}", label_visibility="collapsed")
                if nova_qtd != item['quantidade']:
                    item['quantidade'] = nova_qtd
                    item['subtotal'] = nova_qtd * item['preco_unitario']
                    st.rerun()
                c3.write(f"R$ {formatar_moeda(item['subtotal'])}")
                if c4.button("🗑️", key=f"del_carrinho_{idx}"):
                    st.session_state['carrinho_pdv'].pop(idx)
                    st.rerun()

            st.markdown("---")
            subtotal_geral = sum(i['subtotal'] for i in st.session_state['carrinho_pdv'])
            desconto = st.number_input("Desconto (R$)", min_value=0.0, max_value=float(subtotal_geral), step=1.0, format="%.2f")
            total_final = subtotal_geral - desconto

            st.markdown(f"### Total: R$ {formatar_moeda(total_final)}")

            forma_pagamento = st.radio("Forma de Pagamento", ["dinheiro", "pix", "cartao_credito", "cartao_debito", "fiado"], horizontal=True)

            cliente_id_venda = None
            if forma_pagamento == "fiado":
                clientes_resp = supabase.table("clientes").select("id, nome, saldo_devedor, limite_fiado").eq("empresa_id", emp_id).eq("ativo", True).execute()
                if not clientes_resp.data:
                    st.warning("Nenhum cliente cadastrado. Cadastre em 'Fiado (Clientes)' antes de vender fiado.")
                else:
                    opcoes_cli = {f"{c['nome']} (devendo R$ {formatar_moeda(c['saldo_devedor'])})": c['id'] for c in clientes_resp.data}
                    escolha_cli = st.selectbox("Cliente", list(opcoes_cli.keys()))
                    cliente_id_venda = opcoes_cli[escolha_cli]

            if st.button("✅ Finalizar Venda", type="primary", use_container_width=True):
                if forma_pagamento == "fiado" and not cliente_id_venda:
                    mostrar_popup("Selecione o cliente para venda fiado.", tipo="erro")
                else:
                    try:
                        nova_venda = supabase.table("vendas").insert({
                            "empresa_id": emp_id, "caixa_id": caixa['id'], "operador_id": usuario_id,
                            "cliente_id": cliente_id_venda, "forma_pagamento": forma_pagamento,
                            "valor_subtotal": subtotal_geral, "desconto": desconto,
                            "valor_total": total_final, "status": "concluida"
                        }).execute()
                        venda_id = nova_venda.data[0]['id']

                        for item in st.session_state['carrinho_pdv']:
                            supabase.table("itens_venda").insert({
                                "venda_id": venda_id, "produto_id": item['produto_id'],
                                "quantidade": item['quantidade'], "preco_unitario": item['preco_unitario'],
                                "subtotal": item['subtotal']
                            }).execute()
                            supabase.table("movimentacoes_estoque").insert({
                                "empresa_id": emp_id, "produto_id": item['produto_id'], "tipo": "venda",
                                "quantidade": item['quantidade'], "referencia_venda_id": venda_id,
                                "operador_id": usuario_id
                            }).execute()

                        st.session_state['carrinho_pdv'] = []
                        mostrar_popup(f"VENDA FINALIZADA! Total: R$ {formatar_moeda(total_final)}")
                        st.rerun()
                    except Exception as e:
                        mostrar_popup(f"Erro ao finalizar venda: {e}", tipo="erro")

# ==============================================================
# 7. MÓDULO FIADO (CLIENTES)
# ==============================================================
def tela_fiado():
    st.title("💳 Fiado - Controle de Clientes")
    tab_lista, tab_cadastro = st.tabs(["📋 Clientes", "➕ Cadastrar Cliente"])

    with tab_cadastro:
        with st.form("form_cliente_fiado"):
            nome_cliente = st.text_input("Nome do Cliente")
            telefone_cliente = st.text_input("Telefone (opcional)", placeholder="(84) 99999-9999")
            limite_fiado = st.number_input("Limite de Fiado (R$) — deixe 0 se não quiser limite definido", min_value=0.0, step=10.0, format="%.2f")
            cadastrar = st.form_submit_button("Cadastrar Cliente")
        if cadastrar:
            if not nome_cliente.strip():
                mostrar_popup("Informe o nome do cliente.", tipo="erro")
            else:
                supabase.table("clientes").insert({
                    "empresa_id": emp_id, "nome": nome_cliente, "telefone": telefone_cliente,
                    "limite_fiado": limite_fiado
                }).execute()
                mostrar_popup("CLIENTE CADASTRADO COM SUCESSO!")
                st.rerun()

    with tab_lista:
        clientes_resp = supabase.table("clientes").select("*").eq("empresa_id", emp_id).eq("ativo", True).order("nome").execute()
        lista_clientes = clientes_resp.data or []

        if not lista_clientes:
            st.info("Nenhum cliente cadastrado ainda. Use a aba 'Cadastrar Cliente'.")
            return

        total_devido_geral = sum(float(c['saldo_devedor']) for c in lista_clientes)
        qtd_devendo = len([c for c in lista_clientes if float(c['saldo_devedor']) > 0])
        col_k1, col_k2, col_k3 = st.columns(3)
        col_k1.metric("👥 Clientes Cadastrados", len(lista_clientes))
        col_k2.metric("🔴 Devendo Atualmente", qtd_devendo)
        col_k3.metric("💰 Total a Receber", f"R$ {formatar_moeda(total_devido_geral)}")
        st.markdown("---")

        busca_cliente = st.text_input("🔍 Buscar cliente pelo nome")
        clientes_filtrados = [c for c in lista_clientes if busca_cliente.lower() in c['nome'].lower()] if busca_cliente else lista_clientes
        clientes_filtrados = sorted(clientes_filtrados, key=lambda x: float(x['saldo_devedor']), reverse=True)

        def _fmt_data_hora(iso_str):
            try:
                return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
            except Exception:
                return iso_str

        for cliente in clientes_filtrados:
            saldo = float(cliente['saldo_devedor'])
            icone_saldo = "🔴" if saldo > 0 else "🟢"
            limite_txt = f" | Limite: R$ {formatar_moeda(cliente['limite_fiado'])}" if cliente.get('limite_fiado') else ""

            with st.expander(f"{icone_saldo} {cliente['nome']} — Deve: R$ {formatar_moeda(saldo)}{limite_txt}"):
                tab_hist, tab_pag, tab_editar = st.tabs(["🧾 Histórico", "💵 Registrar Pagamento", "✏️ Editar"])

                with tab_hist:
                    st.caption("Compras fiado:")
                    vendas_fiado = supabase.table("vendas").select("id, valor_total, criado_em") \
                        .eq("cliente_id", cliente['id']).eq("forma_pagamento", "fiado").order("criado_em", desc=True).execute()
                    if vendas_fiado.data:
                        for v in vendas_fiado.data:
                            st.write(f"🧾 {_fmt_data_hora(v['criado_em'])} — R$ {formatar_moeda(v['valor_total'])}")
                    else:
                        st.caption("Nenhuma compra fiado registrada.")

                    st.markdown("---")
                    st.caption("Pagamentos realizados:")
                    pagamentos = supabase.table("pagamentos_fiado").select("valor, forma_pagamento, criado_em, observacao") \
                        .eq("cliente_id", cliente['id']).order("criado_em", desc=True).execute()
                    if pagamentos.data:
                        for p in pagamentos.data:
                            obs_p = f" — {p['observacao']}" if p.get('observacao') else ""
                            st.write(f"💵 {_fmt_data_hora(p['criado_em'])} — R$ {formatar_moeda(p['valor'])} ({p['forma_pagamento']}){obs_p}")
                    else:
                        st.caption("Nenhum pagamento registrado ainda.")

                with tab_pag:
                    if saldo <= 0:
                        st.success("Cliente está com o fiado quitado. ✅")
                    else:
                        valor_pagamento = st.number_input(
                            "Valor do pagamento", min_value=0.0, max_value=saldo, step=5.0,
                            format="%.2f", key=f"pag_valor_{cliente['id']}"
                        )
                        forma_pag_cliente = st.selectbox(
                            "Forma de Pagamento", ["dinheiro", "pix", "cartao_debito", "cartao_credito"],
                            key=f"pag_forma_{cliente['id']}"
                        )
                        obs_pagamento = st.text_input("Observação (opcional)", key=f"pag_obs_{cliente['id']}")
                        if st.button("💾 Registrar Pagamento", key=f"btn_pag_{cliente['id']}"):
                            if valor_pagamento <= 0:
                                mostrar_popup("Informe um valor maior que zero.", tipo="erro")
                            else:
                                supabase.table("pagamentos_fiado").insert({
                                    "empresa_id": emp_id, "cliente_id": cliente['id'], "valor": valor_pagamento,
                                    "forma_pagamento": forma_pag_cliente, "observacao": obs_pagamento,
                                    "operador_id": usuario_id
                                }).execute()
                                mostrar_popup("PAGAMENTO REGISTRADO COM SUCESSO!")
                                st.rerun()

                with tab_editar:
                    novo_nome_cli = st.text_input("Nome", value=cliente['nome'], key=f"edit_nome_{cliente['id']}")
                    novo_tel_cli = st.text_input("Telefone", value=cliente.get('telefone') or "", key=f"edit_tel_{cliente['id']}")
                    novo_limite_cli = st.number_input(
                        "Limite de Fiado (R$)", min_value=0.0, value=float(cliente.get('limite_fiado') or 0),
                        step=10.0, format="%.2f", key=f"edit_limite_{cliente['id']}"
                    )
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        if st.button("💾 Salvar Alterações", key=f"btn_salvar_cli_{cliente['id']}"):
                            supabase.table("clientes").update({
                                "nome": novo_nome_cli, "telefone": novo_tel_cli, "limite_fiado": novo_limite_cli
                            }).eq("id", cliente['id']).execute()
                            mostrar_popup("CLIENTE ATUALIZADO COM SUCESSO!")
                            st.rerun()
                    with col_e2:
                        if st.button("🚫 Desativar Cliente", key=f"btn_desativar_cli_{cliente['id']}"):
                            if saldo > 0:
                                mostrar_popup("Não é possível desativar: cliente ainda tem saldo devedor.", tipo="erro")
                            else:
                                supabase.table("clientes").update({"ativo": False}).eq("id", cliente['id']).execute()
                                mostrar_popup("CLIENTE DESATIVADO!")
                                st.rerun()

# ==============================================================
# 8. MÓDULO ESTOQUE
# ==============================================================
def status_estoque_cor(atual, minimo):
    atual = float(atual or 0)
    minimo = float(minimo or 0)
    if atual <= 0:
        return "🔴 Sem estoque"
    elif atual <= minimo:
        return "🟡 Estoque baixo"
    else:
        return "🟢 Normal"

def status_validade_produto(data_validade_str):
    if not data_validade_str:
        return ""
    try:
        data_val = datetime.strptime(data_validade_str, "%Y-%m-%d").date()
    except Exception:
        return ""
    dias_restantes = (data_val - date.today()).days
    if dias_restantes < 0:
        return f"🔴 VENCIDO há {abs(dias_restantes)}d"
    elif dias_restantes <= 7:
        return f"🟠 Vence em {dias_restantes}d"
    elif dias_restantes <= 30:
        return f"🟡 Vence em {dias_restantes}d"
    else:
        return "🟢 Ok"

def buscar_categorias():
    resp = supabase.table("categorias").select("id, nome").eq("empresa_id", emp_id).order("nome").execute()
    return resp.data or []

def tela_estoque():
    st.title("📦 Estoque")

    produtos_resp = supabase.table("produtos").select(
        "id, nome, codigo_barras, unidade, preco_custo, preco_venda, estoque_atual, "
        "estoque_minimo, data_validade, ativo, categoria_id, categorias(nome)"
    ).eq("empresa_id", emp_id).eq("ativo", True).order("nome").execute()
    lista_produtos = produtos_resp.data or []

    qtd_estoque_baixo = len([p for p in lista_produtos if float(p['estoque_atual'] or 0) <= float(p['estoque_minimo'] or 0)])
    qtd_sem_estoque = len([p for p in lista_produtos if float(p['estoque_atual'] or 0) <= 0])
    qtd_vencendo = len([
        p for p in lista_produtos
        if p.get('data_validade') and 0 <= (datetime.strptime(p['data_validade'], "%Y-%m-%d").date() - date.today()).days <= 7
    ])
    qtd_vencidos = len([
        p for p in lista_produtos
        if p.get('data_validade') and (datetime.strptime(p['data_validade'], "%Y-%m-%d").date() - date.today()).days < 0
    ])

    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("📦 Produtos Ativos", len(lista_produtos))
    col_k2.metric("🟡 Estoque Baixo", qtd_estoque_baixo)
    col_k3.metric("🟠 Vencendo em 7 dias", qtd_vencendo)
    col_k4.metric("🔴 Vencidos", qtd_vencidos)

    if qtd_vencidos > 0:
        st.error(f"⚠️ Você tem {qtd_vencidos} produto(s) VENCIDO(S) ainda no estoque ativo. Confira na aba Produtos e registre a baixa por perda.")

    st.markdown("---")

    tab_lista, tab_cad, tab_cat, tab_ajuste = st.tabs(["📋 Produtos", "➕ Cadastrar Produto", "🗂️ Categorias", "⚖️ Ajuste Manual"])

    # ----------------------------------------------------------
    # ABA: LISTA DE PRODUTOS
    # ----------------------------------------------------------
    with tab_lista:
        categorias_disp = buscar_categorias()
        mapa_categorias = {c['id']: c['nome'] for c in categorias_disp}

        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            busca_produto = st.text_input("🔍 Buscar por nome ou código de barras", key="busca_produto_estoque")
        with col_f2:
            filtro_categoria = st.selectbox("Categoria", ["Todas"] + [c['nome'] for c in categorias_disp], key="filtro_categoria_estoque")
        with col_f3:
            filtro_alerta = st.selectbox("Filtro rápido", ["Todos", "🟡 Estoque baixo", "🔴 Sem estoque", "⏳ Vencendo/Vencido"], key="filtro_alerta_estoque")

        produtos_filtrados = lista_produtos
        if busca_produto:
            termo = busca_produto.lower()
            produtos_filtrados = [p for p in produtos_filtrados if termo in p['nome'].lower() or termo in (p.get('codigo_barras') or "")]
        if filtro_categoria != "Todas":
            produtos_filtrados = [p for p in produtos_filtrados if mapa_categorias.get(p['categoria_id']) == filtro_categoria]
        if filtro_alerta == "🟡 Estoque baixo":
            produtos_filtrados = [p for p in produtos_filtrados if float(p['estoque_atual'] or 0) <= float(p['estoque_minimo'] or 0) and float(p['estoque_atual'] or 0) > 0]
        elif filtro_alerta == "🔴 Sem estoque":
            produtos_filtrados = [p for p in produtos_filtrados if float(p['estoque_atual'] or 0) <= 0]
        elif filtro_alerta == "⏳ Vencendo/Vencido":
            produtos_filtrados = [
                p for p in produtos_filtrados
                if p.get('data_validade') and (datetime.strptime(p['data_validade'], "%Y-%m-%d").date() - date.today()).days <= 30
            ]

        st.caption(f"{len(produtos_filtrados)} produto(s) encontrado(s)")

        for p in produtos_filtrados:
            nome_cat = mapa_categorias.get(p['categoria_id'], "Sem categoria")
            status_est = status_estoque_cor(p['estoque_atual'], p['estoque_minimo'])
            status_val = status_validade_produto(p.get('data_validade'))
            titulo_exp = f"{p['nome']} — {status_est}"
            if status_val and "🟢" not in status_val:
                titulo_exp += f" | {status_val}"

            with st.expander(titulo_exp):
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    st.write(f"**Categoria:** {nome_cat}")
                    st.write(f"**Código de barras:** {p.get('codigo_barras') or '-'}")
                    st.write(f"**Unidade:** {p.get('unidade') or 'un'}")
                    st.write(f"**Estoque atual:** {p['estoque_atual']} (mínimo: {p['estoque_minimo']})")
                with col_i2:
                    st.write(f"**Preço de custo:** R$ {formatar_moeda(p['preco_custo'])}")
                    st.write(f"**Preço de venda:** R$ {formatar_moeda(p['preco_venda'])}")
                    custo_f = float(p['preco_custo'] or 0)
                    venda_f = float(p['preco_venda'] or 0)
                    margem = ((venda_f - custo_f) / custo_f * 100) if custo_f > 0 else 0
                    st.write(f"**Margem:** {margem:.1f}%")
                    if p.get('data_validade'):
                        st.write(f"**Validade:** {datetime.strptime(p['data_validade'], '%Y-%m-%d').strftime('%d/%m/%Y')} ({status_val})")

                st.markdown("---")
                st.caption("✏️ Editar produto")
                col_e1, col_e2, col_e3 = st.columns(3)
                with col_e1:
                    novo_preco_custo = st.number_input("Preço Custo", min_value=0.0, value=float(p['preco_custo'] or 0), step=0.5, format="%.2f", key=f"edit_custo_{p['id']}")
                with col_e2:
                    novo_preco_venda = st.number_input("Preço Venda", min_value=0.0, value=float(p['preco_venda'] or 0), step=0.5, format="%.2f", key=f"edit_venda_{p['id']}")
                with col_e3:
                    novo_minimo = st.number_input("Estoque Mínimo", min_value=0.0, value=float(p['estoque_minimo'] or 0), step=1.0, key=f"edit_min_{p['id']}")

                usa_validade_edit = st.checkbox("Produto tem validade?", value=bool(p.get('data_validade')), key=f"edit_usa_val_{p['id']}")
                nova_validade = None
                if usa_validade_edit:
                    valor_val_atual = datetime.strptime(p['data_validade'], "%Y-%m-%d").date() if p.get('data_validade') else date.today()
                    nova_validade = st.date_input("Data de Validade", value=valor_val_atual, format="DD/MM/YYYY", key=f"edit_val_{p['id']}")

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("💾 Salvar Alterações", key=f"btn_salvar_prod_{p['id']}"):
                        supabase.table("produtos").update({
                            "preco_custo": novo_preco_custo, "preco_venda": novo_preco_venda,
                            "estoque_minimo": novo_minimo,
                            "data_validade": str(nova_validade) if usa_validade_edit else None
                        }).eq("id", p['id']).execute()
                        mostrar_popup("PRODUTO ATUALIZADO COM SUCESSO!")
                        st.rerun()
                with col_b2:
                    if st.button("🚫 Desativar Produto", key=f"btn_desativar_prod_{p['id']}"):
                        supabase.table("produtos").update({"ativo": False}).eq("id", p['id']).execute()
                        mostrar_popup("PRODUTO DESATIVADO!")
                        st.rerun()

    # ----------------------------------------------------------
    # ABA: CADASTRAR PRODUTO
    # ----------------------------------------------------------
    with tab_cad:
        categorias_disp = buscar_categorias()
        opcoes_cat = {"Sem categoria": None}
        opcoes_cat.update({c['nome']: c['id'] for c in categorias_disp})

        with st.form("form_cadastro_produto"):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nome_novo_prod = st.text_input("Nome do Produto*")
                codigo_barras_novo = st.text_input("Código de Barras (opcional)")
                categoria_escolhida = st.selectbox("Categoria", list(opcoes_cat.keys()))
                unidade_novo = st.selectbox("Unidade", ["un", "kg", "l", "cx"])
            with col_c2:
                preco_custo_novo = st.number_input("Preço de Custo (R$)", min_value=0.0, step=0.5, format="%.2f")
                preco_venda_novo = st.number_input("Preço de Venda (R$)*", min_value=0.0, step=0.5, format="%.2f")
                estoque_inicial = st.number_input("Estoque Inicial", min_value=0.0, step=1.0, value=0.0)
                estoque_minimo_novo = st.number_input("Estoque Mínimo (alerta)", min_value=0.0, step=1.0, value=5.0)

            usa_validade_novo = st.checkbox("Este produto tem data de validade?")
            data_validade_novo = None
            if usa_validade_novo:
                data_validade_novo = st.date_input("Data de Validade", format="DD/MM/YYYY")

            cadastrar_prod = st.form_submit_button("💾 Cadastrar Produto")

        if cadastrar_prod:
            if not nome_novo_prod.strip() or preco_venda_novo <= 0:
                mostrar_popup("Informe ao menos o nome e o preço de venda.", tipo="erro")
            else:
                try:
                    novo_produto = supabase.table("produtos").insert({
                        "empresa_id": emp_id,
                        "categoria_id": opcoes_cat[categoria_escolhida],
                        "nome": nome_novo_prod.strip().upper(),
                        "codigo_barras": codigo_barras_novo.strip() or None,
                        "unidade": unidade_novo,
                        "preco_custo": preco_custo_novo,
                        "preco_venda": preco_venda_novo,
                        "estoque_atual": 0,
                        "estoque_minimo": estoque_minimo_novo,
                        "data_validade": str(data_validade_novo) if usa_validade_novo else None,
                        "ativo": True
                    }).execute()
                    produto_id_novo = novo_produto.data[0]['id']

                    if estoque_inicial > 0:
                        supabase.table("movimentacoes_estoque").insert({
                            "empresa_id": emp_id, "produto_id": produto_id_novo, "tipo": "ajuste_entrada",
                            "quantidade": estoque_inicial, "motivo": "Estoque inicial no cadastro",
                            "operador_id": usuario_id
                        }).execute()

                    mostrar_popup("PRODUTO CADASTRADO COM SUCESSO!")
                    st.rerun()
                except Exception as e:
                    mostrar_popup(f"Erro ao cadastrar produto: {e}", tipo="erro")

    # ----------------------------------------------------------
    # ABA: CATEGORIAS
    # ----------------------------------------------------------
    with tab_cat:
        col_cat1, col_cat2 = st.columns([1, 2])
        with col_cat1:
            st.subheader("➕ Nova Categoria")
            nova_categoria_nome = st.text_input("Nome da Categoria", placeholder="Ex: Bebidas, Limpeza, Hortifruti")
            if st.button("Adicionar Categoria"):
                if not nova_categoria_nome.strip():
                    mostrar_popup("Informe o nome da categoria.", tipo="erro")
                else:
                    supabase.table("categorias").insert({"empresa_id": emp_id, "nome": nova_categoria_nome.strip()}).execute()
                    mostrar_popup("CATEGORIA CRIADA COM SUCESSO!")
                    st.rerun()
        with col_cat2:
            st.subheader("📋 Categorias Cadastradas")
            categorias_lista = buscar_categorias()
            if categorias_lista:
                for cat in categorias_lista:
                    col_cn, col_cb = st.columns([4, 1])
                    col_cn.write(cat['nome'])
                    if col_cb.button("🗑️", key=f"del_cat_{cat['id']}"):
                        produtos_na_categoria = supabase.table("produtos").select("id").eq("categoria_id", cat['id']).execute()
                        if produtos_na_categoria.data:
                            mostrar_popup("Não é possível excluir: existem produtos nessa categoria.", tipo="erro")
                        else:
                            supabase.table("categorias").delete().eq("id", cat['id']).execute()
                            st.rerun()
            else:
                st.caption("Nenhuma categoria cadastrada ainda.")

    # ----------------------------------------------------------
    # ABA: AJUSTE MANUAL DE ESTOQUE
    # ----------------------------------------------------------
    with tab_ajuste:
        st.subheader("⚖️ Ajuste Manual de Estoque")
        st.caption("Use para corrigir contagem, registrar perda/quebra, ou entrada de mercadoria fora do fluxo de Compras.")

        if not lista_produtos:
            st.info("Nenhum produto cadastrado ainda.")
        else:
            opcoes_prod_ajuste = {f"{p['nome']} (Atual: {p['estoque_atual']})": p for p in lista_produtos}
            escolha_prod_ajuste = st.selectbox("Produto", list(opcoes_prod_ajuste.keys()), key="select_ajuste_produto")
            produto_ajuste = opcoes_prod_ajuste[escolha_prod_ajuste]

            tipo_ajuste = st.radio(
                "Tipo de Ajuste",
                ["➕ Entrada (corrigir para mais)", "➖ Perda/Quebra (corrigir para menos)"],
                key="radio_tipo_ajuste"
            )
            quantidade_ajuste = st.number_input("Quantidade", min_value=0.0, step=1.0, key="qtd_ajuste_estoque")
            motivo_ajuste = st.text_input("Motivo (obrigatório)", placeholder="Ex: contagem física, produto quebrado, vencido", key="motivo_ajuste_estoque")

            if st.button("💾 Registrar Ajuste", key="btn_registrar_ajuste"):
                if quantidade_ajuste <= 0:
                    mostrar_popup("Informe uma quantidade maior que zero.", tipo="erro")
                elif not motivo_ajuste.strip():
                    mostrar_popup("Informe o motivo do ajuste.", tipo="erro")
                else:
                    tipo_bd = "ajuste_entrada" if tipo_ajuste.startswith("➕") else "ajuste_saida"
                    if tipo_bd == "ajuste_saida" and quantidade_ajuste > float(produto_ajuste['estoque_atual'] or 0):
                        mostrar_popup("Quantidade maior que o estoque atual do produto.", tipo="erro")
                    else:
                        supabase.table("movimentacoes_estoque").insert({
                            "empresa_id": emp_id, "produto_id": produto_ajuste['id'], "tipo": tipo_bd,
                            "quantidade": quantidade_ajuste, "motivo": motivo_ajuste, "operador_id": usuario_id
                        }).execute()
                        mostrar_popup("AJUSTE REGISTRADO COM SUCESSO!")
                        st.rerun()

# ==============================================================
# 9. MÓDULO COMPRAS (FORNECEDORES + PEDIDOS)
# ==============================================================
def buscar_fornecedores():
    resp = supabase.table("fornecedores").select("*").eq("empresa_id", emp_id).order("nome").execute()
    return resp.data or []

def tela_compras():
    st.title("🛒 Compras")

    tab_pedidos, tab_novo, tab_forn = st.tabs(["📋 Pedidos", "➕ Novo Pedido", "🏢 Fornecedores"])

    # ----------------------------------------------------------
    # ABA: FORNECEDORES
    # ----------------------------------------------------------
    with tab_forn:
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            st.subheader("➕ Novo Fornecedor")
            nome_forn = st.text_input("Nome do Fornecedor")
            tel_forn = st.text_input("Telefone (opcional)")
            obs_forn = st.text_input("Observação (opcional)")
            if st.button("Cadastrar Fornecedor"):
                if not nome_forn.strip():
                    mostrar_popup("Informe o nome do fornecedor.", tipo="erro")
                else:
                    supabase.table("fornecedores").insert({
                        "empresa_id": emp_id, "nome": nome_forn.strip(),
                        "telefone": tel_forn, "observacao": obs_forn
                    }).execute()
                    mostrar_popup("FORNECEDOR CADASTRADO COM SUCESSO!")
                    st.rerun()
        with col_f2:
            st.subheader("📋 Fornecedores Cadastrados")
            fornecedores_lista = buscar_fornecedores()
            if fornecedores_lista:
                for f in fornecedores_lista:
                    with st.expander(f['nome']):
                        st.write(f"**Telefone:** {f.get('telefone') or '-'}")
                        st.write(f"**Observação:** {f.get('observacao') or '-'}")
                        if st.button("🗑️ Excluir Fornecedor", key=f"del_forn_{f['id']}"):
                            pedidos_vinculados = supabase.table("compras").select("id").eq("fornecedor_id", f['id']).execute()
                            if pedidos_vinculados.data:
                                mostrar_popup("Não é possível excluir: este fornecedor já tem pedidos registrados.", tipo="erro")
                            else:
                                supabase.table("fornecedores").delete().eq("id", f['id']).execute()
                                mostrar_popup("FORNECEDOR EXCLUÍDO!")
                                st.rerun()
            else:
                st.caption("Nenhum fornecedor cadastrado ainda.")

    # ----------------------------------------------------------
    # ABA: NOVO PEDIDO
    # ----------------------------------------------------------
    with tab_novo:
        fornecedores_lista = buscar_fornecedores()
        if not fornecedores_lista:
            st.warning("Cadastre ao menos 1 fornecedor na aba 'Fornecedores' antes de criar um pedido.")
        else:
            opcoes_forn = {f['nome']: f['id'] for f in fornecedores_lista}
            fornecedor_escolhido = st.selectbox("Fornecedor", list(opcoes_forn.keys()), key="select_fornecedor_pedido")

            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                numero_pedido_novo = st.text_input("Nº do Pedido/Nota (opcional)", key="numero_pedido_novo")
            with col_p2:
                data_prevista_novo = st.date_input("Previsão de Chegada", value=date.today(), format="DD/MM/YYYY", key="data_prevista_novo")
            with col_p3:
                forma_pag_compra = st.selectbox("Forma de Pagamento", ["Não informado", "Pix", "Cartão", "Dinheiro", "Boleto", "Outro"], key="forma_pag_compra_novo")

            obs_pedido_novo = st.text_area("Observação (opcional)", key="obs_pedido_novo")

            st.markdown("---")
            st.subheader("📦 Itens do Pedido")

            if 'carrinho_compra' not in st.session_state:
                st.session_state['carrinho_compra'] = []

            produtos_todos_compra = supabase.table("produtos").select("id, nome, preco_custo") \
                .eq("empresa_id", emp_id).eq("ativo", True).order("nome").execute().data or []

            if not produtos_todos_compra:
                st.warning("Cadastre produtos no módulo Estoque antes de montar um pedido de compra.")
            else:
                opcoes_prod_compra = {p['nome']: p for p in produtos_todos_compra}

                col_ip1, col_ip2, col_ip3, col_ip4 = st.columns([2, 1, 1, 1])
                with col_ip1:
                    produto_escolhido_compra = st.selectbox("Produto", list(opcoes_prod_compra.keys()), key="select_prod_compra")
                with col_ip2:
                    qtd_item_compra = st.number_input("Qtd", min_value=0.0, step=1.0, key="qtd_item_compra")
                with col_ip3:
                    valor_unit_padrao = float(opcoes_prod_compra[produto_escolhido_compra]['preco_custo'] or 0)
                    valor_unit_compra = st.number_input("Valor Unit (R$)", min_value=0.0, step=0.5, value=valor_unit_padrao, format="%.2f", key="valor_unit_item_compra")
                with col_ip4:
                    st.write("")
                    st.write("")
                    if st.button("➕ Adicionar Item", key="btn_add_item_compra"):
                        if qtd_item_compra > 0:
                            prod_sel = opcoes_prod_compra[produto_escolhido_compra]
                            st.session_state['carrinho_compra'].append({
                                'produto_id': prod_sel['id'], 'nome': prod_sel['nome'],
                                'quantidade': qtd_item_compra, 'valor_unitario': valor_unit_compra,
                                'subtotal': qtd_item_compra * valor_unit_compra
                            })
                            st.rerun()
                        else:
                            mostrar_popup("Informe uma quantidade maior que zero.", tipo="erro")

                if st.session_state['carrinho_compra']:
                    st.markdown("**Itens adicionados:**")
                    total_pedido = 0.0
                    for idx, item in enumerate(st.session_state['carrinho_compra']):
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 0.6])
                        c1.write(item['nome'])
                        c2.write(f"{item['quantidade']}x")
                        c3.write(f"R$ {formatar_moeda(item['subtotal'])}")
                        if c4.button("🗑️", key=f"del_item_compra_{idx}"):
                            st.session_state['carrinho_compra'].pop(idx)
                            st.rerun()
                        total_pedido += item['subtotal']

                    st.markdown(f"### Total do Pedido: R$ {formatar_moeda(total_pedido)}")

                    if st.button("✅ Registrar Pedido", type="primary", key="btn_registrar_pedido"):
                        try:
                            novo_pedido = supabase.table("compras").insert({
                                "empresa_id": emp_id, "fornecedor_id": opcoes_forn[fornecedor_escolhido],
                                "numero_pedido": numero_pedido_novo, "status": "aguardando",
                                "data_prevista_chegada": str(data_prevista_novo),
                                "valor_total": total_pedido, "forma_pagamento": forma_pag_compra,
                                "observacao": obs_pedido_novo
                            }).execute()
                            pedido_id_novo = novo_pedido.data[0]['id']

                            for item in st.session_state['carrinho_compra']:
                                supabase.table("itens_compra").insert({
                                    "compra_id": pedido_id_novo, "produto_id": item['produto_id'],
                                    "quantidade": item['quantidade'], "valor_unitario": item['valor_unitario']
                                }).execute()

                            st.session_state['carrinho_compra'] = []
                            mostrar_popup("PEDIDO REGISTRADO COM SUCESSO! Ele vai aparecer em 'Pedidos' como Aguardando.")
                            st.rerun()
                        except Exception as e:
                            mostrar_popup(f"Erro ao registrar pedido: {e}", tipo="erro")
                else:
                    st.caption("Nenhum item adicionado ainda.")

    # ----------------------------------------------------------
    # ABA: PEDIDOS (listagem + marcar chegada)
    # ----------------------------------------------------------
    with tab_pedidos:
        filtro_status_pedido = st.multiselect(
            "Filtrar por Status", ["aguardando", "chegou", "cancelado"],
            default=["aguardando"], key="filtro_status_pedidos"
        )
        pedidos_resp = supabase.table("compras").select("*, fornecedores(nome)") \
            .eq("empresa_id", emp_id).order("data_pedido", desc=True).execute()
        pedidos_lista = pedidos_resp.data or []
        pedidos_filtrados = [p for p in pedidos_lista if p['status'] in filtro_status_pedido] if filtro_status_pedido else pedidos_lista

        qtd_aguardando = len([p for p in pedidos_lista if p['status'] == 'aguardando'])
        st.caption(f"📦 {qtd_aguardando} pedido(s) aguardando chegada no total")
        st.markdown("---")

        if not pedidos_filtrados:
            st.info("Nenhum pedido encontrado com esse filtro.")
        else:
            for pedido in pedidos_filtrados:
                nome_forn_pedido = pedido['fornecedores']['nome'] if pedido.get('fornecedores') else "Fornecedor não informado"
                icone_status = {"aguardando": "⏳", "chegou": "✅", "cancelado": "❌"}.get(pedido['status'], "")
                data_prev_fmt = pedido.get('data_prevista_chegada') or "-"
                titulo_pedido = f"{icone_status} Pedido #{pedido['id']} — {nome_forn_pedido} — R$ {formatar_moeda(pedido['valor_total'])} — Previsão: {data_prev_fmt}"

                with st.expander(titulo_pedido):
                    itens_pedido = supabase.table("itens_compra").select("produto_id, quantidade, valor_unitario, produtos(nome)") \
                        .eq("compra_id", pedido['id']).execute().data or []
                    for it in itens_pedido:
                        nome_prod_it = it['produtos']['nome'] if it.get('produtos') else f"Produto #{it['produto_id']}"
                        st.write(f"- {it['quantidade']}x {nome_prod_it} — R$ {formatar_moeda(it['valor_unitario'])} un.")

                    st.write(f"**Nº do Pedido:** {pedido.get('numero_pedido') or '-'}")
                    st.write(f"**Forma de pagamento:** {pedido.get('forma_pagamento') or '-'}")
                    if pedido.get('observacao'):
                        st.write(f"**Observação:** {pedido['observacao']}")
                    if pedido['status'] == 'chegou':
                        st.success(f"Recebido em {pedido.get('data_chegada') or '-'}")

                    if pedido['status'] == 'aguardando':
                        col_b1, col_b2 = st.columns(2)
                        with col_b1:
                            if st.button("✅ Marcar como Chegou", key=f"chegou_{pedido['id']}"):
                                for it in itens_pedido:
                                    supabase.table("movimentacoes_estoque").insert({
                                        "empresa_id": emp_id, "produto_id": it['produto_id'], "tipo": "compra",
                                        "quantidade": it['quantidade'], "referencia_compra_id": pedido['id'],
                                        "operador_id": usuario_id
                                    }).execute()
                                supabase.table("compras").update({
                                    "status": "chegou", "data_chegada": str(date.today())
                                }).eq("id", pedido['id']).execute()
                                mostrar_popup("PEDIDO RECEBIDO! Estoque atualizado automaticamente.")
                                st.rerun()
                        with col_b2:
                            if st.button("❌ Cancelar Pedido", key=f"cancelar_{pedido['id']}"):
                                supabase.table("compras").update({"status": "cancelado"}).eq("id", pedido['id']).execute()
                                mostrar_popup("PEDIDO CANCELADO.")
                                st.rerun()

# ==============================================================
# 10. MÓDULO FINANCEIRO
# ==============================================================
def tela_financeiro():
    st.title("💰 Financeiro")

    nomes_meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
                   "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    ano_atual = datetime.now().year

    st.markdown("#### 🗓️ Selecione o Período")
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        ano_selecionado = st.number_input("Ano", min_value=2020, max_value=2100, value=ano_atual, step=1, key="fin_ano")
    with col_p2:
        meses_selecionados_nomes = st.multiselect(
            "Mês (ou meses) — deixe vazio para o ano inteiro",
            nomes_meses, default=[nomes_meses[datetime.now().month - 1]], key="fin_meses"
        )
    meses_selecionados = [nomes_meses.index(m) + 1 for m in meses_selecionados_nomes] if meses_selecionados_nomes else list(range(1, 13))

    def _dentro_periodo(data_str):
        if not data_str:
            return False
        try:
            d = datetime.strptime(str(data_str).split("T")[0], "%Y-%m-%d").date()
            return d.year == ano_selecionado and d.month in meses_selecionados
        except Exception:
            return False

    # ---- Receita (vendas concluídas) ----
    vendas_resp = supabase.table("vendas").select("id, valor_total, forma_pagamento, criado_em") \
        .eq("empresa_id", emp_id).eq("status", "concluida").execute()
    vendas_periodo = [v for v in (vendas_resp.data or []) if _dentro_periodo(v['criado_em'])]
    receita_total = sum(float(v['valor_total']) for v in vendas_periodo)
    qtd_vendas_periodo = len(vendas_periodo)
    ticket_medio = receita_total / qtd_vendas_periodo if qtd_vendas_periodo else 0.0

    receita_por_forma = {}
    for v in vendas_periodo:
        receita_por_forma[v['forma_pagamento']] = receita_por_forma.get(v['forma_pagamento'], 0.0) + float(v['valor_total'])

    # ---- Despesas operacionais avulsas ----
    despesas_resp = supabase.table("despesas").select("*").eq("empresa_id", emp_id).execute()
    despesas_periodo = [d for d in (despesas_resp.data or []) if _dentro_periodo(d.get('data_despesa'))]
    total_despesas = sum(float(d['valor']) for d in despesas_periodo)

    # ---- Compras de mercadoria já recebidas ----
    compras_resp = supabase.table("compras").select("*, fornecedores(nome)").eq("empresa_id", emp_id).eq("status", "chegou").execute()
    compras_periodo = [c for c in (compras_resp.data or []) if _dentro_periodo(c.get('data_chegada'))]
    total_compras = sum(float(c['valor_total'] or 0) for c in compras_periodo)

    lucro_liquido = receita_total - total_despesas - total_compras

    st.markdown(f"#### 📊 Resumo — {', '.join(meses_selecionados_nomes) if meses_selecionados_nomes else 'Ano inteiro'} de {ano_selecionado}")
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    col_r1.metric("💵 Receita (Vendas)", f"R$ {formatar_moeda(receita_total)}", help=f"{qtd_vendas_periodo} venda(s)")
    col_r2.metric("📦 Compras de Mercadoria", f"R$ {formatar_moeda(total_compras)}")
    col_r3.metric("📉 Despesas Operacionais", f"R$ {formatar_moeda(total_despesas)}")
    col_r4.metric("✨ Lucro Líquido", f"R$ {formatar_moeda(lucro_liquido)}",
                  delta="Positivo" if lucro_liquido >= 0 else "Atenção",
                  delta_color="normal" if lucro_liquido >= 0 else "inverse")
    st.caption(f"🎟️ Ticket médio por venda: R$ {formatar_moeda(ticket_medio)}")

    clientes_saldo_resp = supabase.table("clientes").select("saldo_devedor").eq("empresa_id", emp_id).execute()
    total_fiado_pendente = sum(float(c['saldo_devedor'] or 0) for c in (clientes_saldo_resp.data or []))
    if total_fiado_pendente > 0:
        st.info(f"💳 R$ {formatar_moeda(total_fiado_pendente)} em fiado pendente de recebimento no total (já contabilizado na receita, mas ainda não está fisicamente no caixa).")

    st.markdown("---")
    st.markdown("#### 💳 Vendas por Forma de Pagamento")
    if receita_por_forma:
        df_formas = pd.DataFrame([{"Forma": k.replace("_", " ").title(), "Valor": v} for k, v in receita_por_forma.items()])
        st.bar_chart(df_formas.set_index("Forma"))
    else:
        st.caption("Nenhuma venda registrada neste período.")

    st.markdown("---")
    with st.expander("➕ Registrar Despesa Operacional (aluguel, luz, água, salário...)", expanded=False):
        with st.form("form_despesa_operacional"):
            categoria_despesa = st.selectbox("Categoria", ["Aluguel", "Energia", "Água", "Salário", "Manutenção", "Fornecedor de Serviço", "Outros"])
            descricao_despesa = st.text_input("Descrição")
            valor_despesa = st.number_input("Valor (R$)", min_value=0.0, step=5.0, format="%.2f")
            data_despesa_input = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            registrar_despesa = st.form_submit_button("Registrar Despesa")
        if registrar_despesa:
            if valor_despesa <= 0:
                mostrar_popup("Informe um valor maior que zero.", tipo="erro")
            else:
                supabase.table("despesas").insert({
                    "empresa_id": emp_id, "categoria": categoria_despesa, "descricao": descricao_despesa,
                    "valor": valor_despesa, "data_despesa": str(data_despesa_input)
                }).execute()
                mostrar_popup("DESPESA REGISTRADA COM SUCESSO!")
                st.rerun()

    st.markdown("#### 📜 Extrato de Despesas Operacionais do Período")
    if despesas_periodo:
        df_desp_show = pd.DataFrame(despesas_periodo)[["data_despesa", "categoria", "descricao", "valor"]].copy()
        df_desp_show = df_desp_show.sort_values("data_despesa", ascending=False)
        df_desp_show["data_despesa"] = df_desp_show["data_despesa"].apply(
            lambda d: datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
        )
        st.dataframe(df_desp_show, use_container_width=True, hide_index=True)

        with st.expander("✏️ Editar ou Excluir uma Despesa", expanded=False):
            opcoes_desp = {
                f"{datetime.strptime(str(d['data_despesa']).split('T')[0], '%Y-%m-%d').strftime('%d/%m/%Y')} — {d['categoria']} — R$ {float(d['valor']):.2f}": d['id']
                for d in despesas_periodo
            }
            escolha_desp = st.selectbox("Selecione a despesa", list(opcoes_desp.keys()), key="select_edit_despesa")
            despesa_sel = next(d for d in despesas_periodo if d['id'] == opcoes_desp[escolha_desp])

            col_ed1, col_ed2 = st.columns(2)
            with col_ed1:
                categoria_edit = st.selectbox(
                    "Categoria", ["Aluguel", "Energia", "Água", "Salário", "Manutenção", "Fornecedor de Serviço", "Outros"],
                    index=(["Aluguel", "Energia", "Água", "Salário", "Manutenção", "Fornecedor de Serviço", "Outros"].index(despesa_sel['categoria'])
                           if despesa_sel['categoria'] in ["Aluguel", "Energia", "Água", "Salário", "Manutenção", "Fornecedor de Serviço", "Outros"] else 0),
                    key="edit_categoria_desp_fin"
                )
            with col_ed2:
                valor_edit = st.number_input("Valor (R$)", min_value=0.0, value=float(despesa_sel['valor']), step=5.0, format="%.2f", key="edit_valor_desp_fin")
            descricao_edit = st.text_input("Descrição", value=despesa_sel.get('descricao') or "", key="edit_desc_desp_fin")
            data_edit = st.date_input(
                "Data", value=datetime.strptime(str(despesa_sel['data_despesa']).split("T")[0], "%Y-%m-%d").date(),
                format="DD/MM/YYYY", key="edit_data_desp_fin"
            )

            col_be1, col_be2 = st.columns(2)
            with col_be1:
                if st.button("💾 Salvar Alteração", key="btn_salvar_desp_fin"):
                    supabase.table("despesas").update({
                        "categoria": categoria_edit, "descricao": descricao_edit,
                        "valor": valor_edit, "data_despesa": str(data_edit)
                    }).eq("id", despesa_sel['id']).execute()
                    mostrar_popup("DESPESA ATUALIZADA COM SUCESSO!")
                    st.rerun()
            with col_be2:
                if st.button("🗑️ Excluir Despesa", key="btn_excluir_desp_fin"):
                    supabase.table("despesas").delete().eq("id", despesa_sel['id']).execute()
                    mostrar_popup("DESPESA EXCLUÍDA!")
                    st.rerun()
    else:
        st.caption("Nenhuma despesa operacional registrada neste período.")

    st.markdown("---")
    st.markdown("#### 📦 Compras de Mercadoria Recebidas no Período")
    if compras_periodo:
        df_compras_show = pd.DataFrame([{
            "Data Chegada": c.get('data_chegada'),
            "Fornecedor": c['fornecedores']['nome'] if c.get('fornecedores') else "-",
            "Nº Pedido": c.get('numero_pedido') or "-",
            "Valor Total": c.get('valor_total') or 0
        } for c in compras_periodo])
        st.dataframe(df_compras_show, use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhuma compra recebida neste período.")

    st.markdown("---")
    st.markdown("#### 📤 Exportar Resumo do Período (Excel)")
    buffer_excel_fin = io.BytesIO()
    with pd.ExcelWriter(buffer_excel_fin, engine="openpyxl") as writer:
        pd.DataFrame([{
            "Período": f"{', '.join(meses_selecionados_nomes) if meses_selecionados_nomes else 'Ano inteiro'} de {ano_selecionado}",
            "Receita (Vendas)": receita_total, "Compras de Mercadoria": total_compras,
            "Despesas Operacionais": total_despesas, "Lucro Líquido": lucro_liquido,
            "Qtd Vendas": qtd_vendas_periodo, "Ticket Médio": ticket_medio
        }]).to_excel(writer, index=False, sheet_name="Resumo")
        if despesas_periodo:
            pd.DataFrame(despesas_periodo)[["data_despesa", "categoria", "descricao", "valor"]].to_excel(writer, index=False, sheet_name="Despesas")
        if compras_periodo:
            df_compras_show.to_excel(writer, index=False, sheet_name="Compras Recebidas")
    buffer_excel_fin.seek(0)
    st.download_button(
        "📊 Baixar Excel do Período", data=buffer_excel_fin,
        file_name=f"financeiro_{ano_selecionado}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ==============================================================
# 11. MÓDULO DASHBOARD
# ==============================================================
def tela_dashboard():
    st.title("📊 Dashboard")
    st.markdown(f"### 👋 Bem-vindo, {nome_usuario}!")
    st.markdown("---")

    hoje = date.today()
    inicio_mes = date(hoje.year, hoje.month, 1)

    def _no_mes_atual(data_str):
        if not data_str:
            return False
        try:
            d = datetime.strptime(str(data_str).split("T")[0], "%Y-%m-%d").date()
            return d.year == hoje.year and d.month == hoje.month
        except Exception:
            return False

    def _hoje(data_str):
        if not data_str:
            return False
        try:
            d = datetime.strptime(str(data_str).split("T")[0], "%Y-%m-%d").date()
            return d == hoje
        except Exception:
            return False

    # ---- Vendas do mês ----
    vendas_resp = supabase.table("vendas").select("id, valor_total, criado_em") \
        .eq("empresa_id", emp_id).eq("status", "concluida").execute()
    vendas_mes = [v for v in (vendas_resp.data or []) if _no_mes_atual(v['criado_em'])]
    vendas_hoje = [v for v in vendas_mes if _hoje(v['criado_em'])]

    receita_mes = sum(float(v['valor_total']) for v in vendas_mes)
    qtd_vendas_mes = len(vendas_mes)
    ticket_medio_mes = receita_mes / qtd_vendas_mes if qtd_vendas_mes else 0.0
    receita_hoje = sum(float(v['valor_total']) for v in vendas_hoje)

    # ---- Despesas e compras do mês ----
    despesas_resp = supabase.table("despesas").select("valor, data_despesa").eq("empresa_id", emp_id).execute()
    despesas_mes = sum(float(d['valor']) for d in (despesas_resp.data or []) if _no_mes_atual(d.get('data_despesa')))

    compras_resp = supabase.table("compras").select("valor_total, data_chegada, status").eq("empresa_id", emp_id).eq("status", "chegou").execute()
    compras_mes = sum(float(c['valor_total'] or 0) for c in (compras_resp.data or []) if _no_mes_atual(c.get('data_chegada')))

    lucro_mes = receita_mes - despesas_mes - compras_mes

    # ---- KPIs principais ----
    col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
    col_k1.metric("💰 Receita do Mês", f"R$ {formatar_moeda(receita_mes)}")
    col_k2.metric("✨ Lucro do Mês", f"R$ {formatar_moeda(lucro_mes)}", delta="Positivo" if lucro_mes >= 0 else "Atenção", delta_color="normal" if lucro_mes >= 0 else "inverse")
    col_k3.metric("🎟️ Ticket Médio", f"R$ {formatar_moeda(ticket_medio_mes)}")
    col_k4.metric("🛒 Vendas Hoje", len(vendas_hoje), delta=f"R$ {formatar_moeda(receita_hoje)}")
    col_k5.metric("📅 Vendas no Mês", qtd_vendas_mes)

    st.markdown("---")

    # ---- Painel de alertas ----
    produtos_resp = supabase.table("produtos").select("id, nome, estoque_atual, estoque_minimo, data_validade").eq("empresa_id", emp_id).eq("ativo", True).execute()
    produtos_ativos = produtos_resp.data or []
    qtd_estoque_baixo = len([p for p in produtos_ativos if float(p['estoque_atual'] or 0) <= float(p['estoque_minimo'] or 0)])
    produtos_vencendo = [
        p for p in produtos_ativos
        if p.get('data_validade') and 0 <= (datetime.strptime(p['data_validade'], "%Y-%m-%d").date() - hoje).days <= 7
    ]

    clientes_saldo_resp = supabase.table("clientes").select("saldo_devedor").eq("empresa_id", emp_id).execute()
    total_fiado_pendente = sum(float(c['saldo_devedor'] or 0) for c in (clientes_saldo_resp.data or []))

    pedidos_aguardando_resp = supabase.table("compras").select("id").eq("empresa_id", emp_id).eq("status", "aguardando").execute()
    qtd_pedidos_aguardando = len(pedidos_aguardando_resp.data or [])

    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    col_a1.metric("🟡 Estoque Baixo", qtd_estoque_baixo)
    col_a2.metric("🟠 Vencendo em 7 dias", len(produtos_vencendo))
    col_a3.metric("💳 Fiado a Receber", f"R$ {formatar_moeda(total_fiado_pendente)}")
    col_a4.metric("📦 Pedidos Aguardando", qtd_pedidos_aguardando)

    if produtos_vencendo:
        with st.expander(f"🟠 Ver os {len(produtos_vencendo)} produto(s) vencendo em breve"):
            for p in produtos_vencendo:
                dias_rest = (datetime.strptime(p['data_validade'], "%Y-%m-%d").date() - hoje).days
                st.write(f"- **{p['nome']}** — vence em {dias_rest} dia(s)")

    st.markdown("---")

    # ---- Evolução diária de vendas no mês ----
    col_g1, col_g2 = st.columns([1.6, 1])

    with col_g1:
        st.subheader("📈 Vendas Diárias do Mês")
        if vendas_mes:
            df_vendas_mes = pd.DataFrame(vendas_mes)
            df_vendas_mes['Data'] = pd.to_datetime(df_vendas_mes['criado_em'].str.split("T").str[0])
            df_diario = df_vendas_mes.groupby('Data')['valor_total'].sum().reset_index()
            df_diario.columns = ['Data', 'Receita']
            df_diario['Receita'] = df_diario['Receita'].astype(float)

            fig_evolucao = px.area(df_diario, x="Data", y="Receita", template="plotly_dark")
            fig_evolucao.update_traces(line_color="#FFC107", fillcolor="rgba(255,193,7,0.2)")
            fig_evolucao.update_layout(margin=dict(t=20, b=0, l=0, r=0), yaxis=dict(title=""), xaxis=dict(title=""))
            st.plotly_chart(fig_evolucao, use_container_width=True)
        else:
            st.info("Nenhuma venda registrada neste mês ainda.")

    with col_g2:
        st.subheader("🏆 Top 5 Produtos (mês)")
        ids_vendas_mes = [v['id'] for v in vendas_mes]

        if ids_vendas_mes:
            itens_venda_resp = supabase.table("itens_venda").select("produto_id, quantidade").in_("venda_id", ids_vendas_mes).execute()
            itens_mes = itens_venda_resp.data or []
        else:
            itens_mes = []

        if itens_mes:
            mapa_nomes_prod = {p['id']: p['nome'] for p in produtos_ativos}
            uso_produtos = {}
            for it in itens_mes:
                pid = it['produto_id']
                uso_produtos[pid] = uso_produtos.get(pid, 0) + float(it['quantidade'])

            df_top = pd.DataFrame([
                {"Produto": mapa_nomes_prod.get(pid, f"Produto #{pid}"), "Qtd": qtd}
                for pid, qtd in uso_produtos.items()
            ]).sort_values("Qtd", ascending=True).tail(5)

            fig_top = px.bar(df_top, x="Qtd", y="Produto", orientation='h', template="plotly_dark", color_discrete_sequence=["#FFC107"])
            fig_top.update_layout(showlegend=False, margin=dict(t=10, b=0, l=0, r=0), xaxis=dict(title="", showticklabels=False), yaxis=dict(title=""))
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.info("Sem vendas suficientes para ranking ainda.")

    st.markdown("---")
    st.subheader("📦 Próximos Pedidos Aguardando Chegada")
    pedidos_prox_resp = supabase.table("compras").select("id, numero_pedido, valor_total, data_prevista_chegada, fornecedores(nome)") \
        .eq("empresa_id", emp_id).eq("status", "aguardando").order("data_prevista_chegada").limit(5).execute()
    if pedidos_prox_resp.data:
        for pedido in pedidos_prox_resp.data:
            nome_forn = pedido['fornecedores']['nome'] if pedido.get('fornecedores') else "Fornecedor não informado"
            st.write(f"⏳ **{pedido.get('data_prevista_chegada') or '-'}** — {nome_forn} — R$ {formatar_moeda(pedido['valor_total'])}")
    else:
        st.caption("Nenhum pedido aguardando chegada no momento.")

# ==============================================================
# 12. MÓDULO ADMIN: GESTÃO DE ASSINANTES
# ==============================================================
def tela_gestao_assinantes():
    st.title("👑 Gestão de Assinantes")
    st.caption("Painel restrito ao administrador do sistema (visão de todos os mercadinhos assinantes).")

    usuarios_resp = supabase.table("usuarios").select(
        "id, nome, email, ativo, senha_hash, email_confirmado, metodo_pagamento, comprovante_pagamento, empresa_id, empresas(nome_fantasia)"
    ).neq("perfil", "admin_geral").execute()
    usuarios_lista = usuarios_resp.data or []

    if not usuarios_lista:
        st.info("Nenhum mercadinho cadastrado ainda.")
        return

    for u in usuarios_lista:
        assinatura_resp = supabase.table("assinaturas").select("data_inicio, data_vencimento") \
            .eq("empresa_id", u['empresa_id']).order("data_vencimento", desc=True).limit(1).execute()
        venc = assinatura_resp.data[0]['data_vencimento'] if assinatura_resp.data else "Sem assinatura"
        nome_fantasia = u['empresas']['nome_fantasia'] if u.get('empresas') else "Sem Empresa"
        aguardando_manual = (u.get('metodo_pagamento') == "manual") and (not u['ativo'])
        icone_email = "✅" if u.get('email_confirmado') else "❌ e-mail não confirmado"

        titulo = f"🏢 {nome_fantasia} — {u['nome']} ({u['email']}) | Validade: {venc} | {icone_email}"
        if aguardando_manual:
            titulo = "🔔 " + titulo + " | ⏳ Aguardando confirmação manual"

        with st.expander(titulo):
            if aguardando_manual:
                st.warning("⏳ Este mercadinho escolheu 'pagar em mãos' e aguarda confirmação.")
                if u.get('comprovante_pagamento'):
                    st.info(f"📎 Descrição enviada: {u['comprovante_pagamento']}")
                if st.button("✅ Confirmar Pagamento Recebido", key=f"conf_manual_{u['id']}"):
                    ativar_conta_apos_pagamento(u['id'], "manual")
                    mostrar_popup("Conta ativada com sucesso!")
                    st.rerun()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"Status: **{'Ativo' if u['ativo'] else 'Bloqueado'}**")
                if st.button("Bloquear/Desbloquear", key=f"blk_{u['id']}"):
                    supabase.table("usuarios").update({"ativo": not u['ativo']}).eq("id", u['id']).execute()
                    st.rerun()
            with col2:
                nova_senha_admin = st.text_input("Nova Senha", key=f"pwd_{u['id']}")
                if st.button("Mudar Senha", key=f"btn_pwd_{u['id']}") and nova_senha_admin:
                    supabase.table("usuarios").update({"senha_hash": nova_senha_admin}).eq("id", u['id']).execute()
                    mostrar_popup("Senha alterada!")
            with col3:
                meses_add = st.number_input("Estender (meses)", min_value=1, value=1, key=f"mes_{u['id']}")
                if st.button("Renovar Assinatura", key=f"ren_{u['id']}"):
                    try:
                        data_base = datetime.strptime(venc, "%Y-%m-%d") if venc != "Sem assinatura" and datetime.strptime(venc, "%Y-%m-%d") > datetime.now() else datetime.now()
                    except Exception:
                        data_base = datetime.now()
                    novo_venc = data_base + relativedelta(months=meses_add)
                    supabase.table("assinaturas").update({
                        "data_vencimento": novo_venc.strftime("%Y-%m-%d")
                    }).eq("empresa_id", u['empresa_id']).execute()
                    mostrar_popup("Assinatura renovada!")
                    st.rerun()

# ==============================================================
# 13. ROTEAMENTO DOS MÓDULOS
# ==============================================================
if menu == "👑 Gestão de Assinantes":
    tela_gestao_assinantes()

elif menu == "🧾 PDV":
    caixa_atual = buscar_caixa_aberto()
    if not caixa_atual:
        tela_abrir_caixa()
    else:
        tela_pdv(caixa_atual)

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
