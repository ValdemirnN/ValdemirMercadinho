"""
auth.py
Tudo relacionado a: login, criação de conta, confirmação de e-mail, fluxo de
pagamento da assinatura, restauração de sessão via token na URL, logout, e os
helpers de PERMISSÃO POR PERFIL usados no resto do sistema.

Perfis existentes:
    admin_geral -> dono do sistema (gerencia todos os mercadinhos assinantes)
    dono        -> dono do mercadinho (criado no cadastro), acesso completo
    gerente     -> criado pelo dono na aba "Equipe", acesso completo
    operador    -> criado pelo dono/gerente na aba "Equipe", acesso restrito
                   (somente PDV e Fiado, histórico de caixa só o dele, sem
                   ver diferenças/expectativa de caixa)
"""
import streamlit as st
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, date
import requests
from dateutil.relativedelta import relativedelta

from config import (
    supabase, GMAIL_REMETENTE, GMAIL_SENHA_APP, MP_ACCESS_TOKEN,
    URL_BASE_SISTEMA, VALOR_ASSINATURA_MENSAL, SECRET_TOKEN_KEY
)
from utils import formatar_moeda, mostrar_popup

PERFIS_ACESSO_COMPLETO = ("admin_geral", "dono", "gerente")

# Módulos que podem ser liberados como "extra" pra um Operador, além do PDV
# (que ele sempre tem por padrão). Chave = salva em permissoes_extras no banco,
# Label = como aparece no menu lateral e nos checkboxes de cadastro/edição.
MODULOS_EXTRAS_DISPONIVEIS = [
    ("dashboard", "📊 Dashboard"),
    ("estoque", "📦 Estoque"),
    ("compras", "🛒 Compras"),
    ("fiado", "💳 Fiado (Clientes)"),
    ("financeiro", "💰 Financeiro"),
]


# ==============================================================
# HELPERS DE PERMISSÃO (usados em todos os outros módulos)
# ==============================================================
def perfil_atual():
    return st.session_state.get("perfil", "")


def tem_acesso_completo():
    """Dono, gerente e admin_geral enxergam tudo. Operador não."""
    return perfil_atual() in PERFIS_ACESSO_COMPLETO


def is_operador():
    return perfil_atual() == "operador"


def permissoes_extras_atual():
    """Lista de módulos extras liberados para o usuário logado (só importa pra operador)."""
    return st.session_state.get("permissoes_extras") or []


def tem_permissao_extra(modulo):
    """
    Verifica se o usuário logado pode acessar um módulo fora do pacote padrão dele.
    Quem já tem acesso completo (dono/gerente/admin_geral) sempre pode.
    Operador só pode se 'modulo' estiver na lista permissoes_extras salva no cadastro.
    """
    if tem_acesso_completo():
        return True
    return modulo in permissoes_extras_atual()


def pode_ver_diferenca_caixa():
    """Só quem tem acesso completo pode ver sobra/falta e o valor esperado na gaveta."""
    return tem_acesso_completo()


def exigir_acesso_completo():
    """Bloqueia a tela para operadores que tentem acessá-la diretamente."""
    if not tem_acesso_completo():
        st.error("🚫 Você não tem permissão para acessar esta área.")
        st.stop()


# ==============================================================
# TOKEN DE SESSÃO
# ==============================================================
def gerar_token_sessao(usuario_id, senha_hash):
    base = f"{usuario_id}:{senha_hash}:{SECRET_TOKEN_KEY}"
    return hashlib.sha256(base.encode()).hexdigest()[:24]


# ==============================================================
# E-MAIL DE CONFIRMAÇÃO
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
# MERCADO PAGO (assinatura)
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


# ==============================================================
# SESSÃO
# ==============================================================
def restaurar_sessao_por_token():
    try:
        params = st.query_params
        uid_param = params.get("uid")
        tk_param = params.get("tk")
        if uid_param and tk_param:
            usuario_id_restaurar = int(uid_param)
            resultado = supabase.table("usuarios").select(
                "id, nome, senha_hash, perfil, empresa_id, ativo, cargo, permissoes_extras, foto_base64"
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
                            'nome_usuario': usuario['nome'],
                            'cargo': usuario.get('cargo') or '',
                            'permissoes_extras': usuario.get('permissoes_extras') or [],
                            'foto_base64': usuario.get('foto_base64') or ''
                        })
                    else:
                        st.query_params.clear()
    except Exception:
        pass


def fazer_logout():
    st.session_state.update({
        'logado': False, 'perfil': '', 'empresa_id': None,
        'usuario_id': None, 'nome_usuario': '', 'cargo': '', 'permissoes_extras': [],
        'foto_base64': ''
    })
    st.query_params.clear()


def inicializar_sessao():
    if 'logado' not in st.session_state:
        st.session_state.update({
            'logado': False, 'perfil': '', 'empresa_id': None,
            'usuario_id': None, 'nome_usuario': '', 'cargo': '', 'permissoes_extras': [],
            'foto_base64': ''
        })
        restaurar_sessao_por_token()

    if st.query_params.get("confirmar_email"):
        confirmar_email_por_link()


# ==============================================================
# TELA DE LOGIN / CADASTRO / PAGAMENTO
# ==============================================================
def tela_login_e_cadastro():
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
        st.markdown("✅ **Múltiplos terminais e equipe** — cada operador com seu próprio caixa")

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
                    "id, nome, senha_hash, perfil, empresa_id, ativo, cargo, permissoes_extras, foto_base64"
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
                                'nome_usuario': usuario['nome'],
                                'cargo': usuario.get('cargo') or '',
                                'permissoes_extras': usuario.get('permissoes_extras') or [],
                                'foto_base64': usuario.get('foto_base64') or ''
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
        st.caption("🆕 Novo mercadinho? Crie a conta do dono abaixo. Operadores e gerentes são cadastrados depois, dentro do sistema, na aba **Equipe**.")
        with st.expander("🆕 Ainda não tem conta? Criar conta do Dono"):
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

                                email_enviado = enviar_email_confirmacao(email_cadastro, nome_usuario_cadastro, token_confirmacao_novo)
                                if email_enviado:
                                    mostrar_popup("Conta criada! Enviamos um e-mail de confirmação — clique no link para prosseguir com o pagamento.")
                                else:
                                    mostrar_popup("Conta criada, mas houve falha ao enviar o e-mail. Veja o erro acima e verifique as credenciais SMTP.", tipo="erro")
                            except Exception as e_criar:
                                mostrar_popup(f"Erro ao criar conta: {e_criar}", tipo="erro")
    st.stop()
