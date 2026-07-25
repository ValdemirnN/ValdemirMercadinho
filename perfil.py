"""
perfil.py
Tela "Meu Perfil": qualquer usuário logado (Dono, Gerente ou Operador) pode
ver e editar os próprios dados — nome, foto e senha. A foto é opcional; se
não for definida, mostra um ícone padrão. A foto é salva como base64 direto
na coluna usuarios.foto_base64 (não depende de bucket de Storage).
"""
import base64
import io
import re
import secrets

import streamlit as st

from config import supabase
from utils import mostrar_popup
from auth import enviar_email_troca_confirmacao

TAMANHO_MAX_FOTO = (300, 300)  # redimensiona pra não pesar no banco
REGEX_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _processar_foto_upload(arquivo_upload):
    """Recebe um arquivo do st.file_uploader, redimensiona e retorna base64 (str) pronto pra salvar."""
    try:
        from PIL import Image
    except ImportError:
        mostrar_popup("Biblioteca Pillow não instalada. Adicione 'Pillow' ao requirements.txt.", tipo="erro")
        return None

    try:
        imagem = Image.open(arquivo_upload)
        imagem = imagem.convert("RGB")
        imagem.thumbnail(TAMANHO_MAX_FOTO)
        buffer = io.BytesIO()
        imagem.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        mostrar_popup(f"Não foi possível processar a imagem: {e}", tipo="erro")
        return None


def tela_meu_perfil():
    st.title("👤 Meu Perfil")
    usuario_id = st.session_state['usuario_id']

    resultado = supabase.table("usuarios").select(
        "nome, email, cargo, perfil, foto_base64, telefone, "
        "endereco_rua, endereco_numero, endereco_bairro, novo_email_pendente"
    ).eq("id", usuario_id).execute()

    if not resultado.data:
        st.error("Não foi possível carregar seus dados.")
        return

    dados_usuario = resultado.data[0]

    col_foto, col_dados = st.columns([1, 2.5])

    with col_foto:
        foto_atual = dados_usuario.get("foto_base64")
        if foto_atual:
            st.markdown(
                f"""<img src="data:image/jpeg;base64,{foto_atual}"
                    style="width:160px;height:160px;border-radius:50%;object-fit:cover;
                    border:3px solid #3B82F6;" />""",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                """<div style="width:160px;height:160px;border-radius:50%;background-color:#5F6368;
                    display:flex;align-items:center;justify-content:center;border:3px solid #3B82F6;">
                    <svg viewBox="0 0 24 24" width="90" height="90" fill="white">
                        <circle cx="12" cy="8" r="4"/>
                        <path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6v1H4v-1z"/>
                    </svg>
                </div>""",
                unsafe_allow_html=True
            )

    with col_dados:
        st.write(f"**Nome:** {dados_usuario['nome']}")
        st.write(f"**E-mail (login):** {dados_usuario['email']}")
        st.write(f"**Cargo:** {dados_usuario.get('cargo') or dados_usuario['perfil'].capitalize()}")
        st.caption("O cargo só pode ser alterado pelo Dono/Gerente, na aba Equipe.")

    st.markdown("---")
    st.subheader("✏️ Editar meus dados")

    with st.form("form_editar_perfil"):
        novo_nome = st.text_input("Nome", value=dados_usuario['nome'])
        novo_telefone = st.text_input(
            "Contato (WhatsApp/telefone)", value=dados_usuario.get('telefone') or "",
            placeholder="(84) 99999-9999"
        )

        st.markdown("**Endereço**")
        col_end1, col_end2 = st.columns([2.5, 1])
        with col_end1:
            nova_rua = st.text_input("Rua", value=dados_usuario.get('endereco_rua') or "")
        with col_end2:
            novo_numero = st.text_input("Número", value=dados_usuario.get('endereco_numero') or "")
        novo_bairro = st.text_input("Bairro", value=dados_usuario.get('endereco_bairro') or "")

        st.markdown("**Foto**")
        nova_foto = st.file_uploader("Foto de perfil (opcional)", type=["png", "jpg", "jpeg"])
        st.caption("Deixe em branco pra manter a foto atual. Envie uma imagem pra trocar.")

        st.markdown("**Alterar senha (opcional)**")
        nova_senha = st.text_input("Nova senha", type="password", placeholder="Deixe em branco pra manter a atual")
        confirma_nova_senha = st.text_input("Confirme a nova senha", type="password")

        salvar = st.form_submit_button("💾 Salvar Alterações", type="primary")

    if salvar:
        if not novo_nome.strip():
            mostrar_popup("O nome não pode ficar em branco.", tipo="erro")
            return

        dados_atualizar = {
            "nome": novo_nome.strip(),
            "telefone": novo_telefone.strip() or None,
            "endereco_rua": nova_rua.strip() or None,
            "endereco_numero": novo_numero.strip() or None,
            "endereco_bairro": novo_bairro.strip() or None,
        }

        if nova_foto is not None:
            foto_base64_processada = _processar_foto_upload(nova_foto)
            if foto_base64_processada is None:
                return
            dados_atualizar["foto_base64"] = foto_base64_processada

        if nova_senha or confirma_nova_senha:
            if nova_senha != confirma_nova_senha:
                mostrar_popup("As senhas não coincidem.", tipo="erro")
                return
            if len(nova_senha) < 7:
                mostrar_popup("A senha precisa ter no mínimo 7 caracteres.", tipo="erro")
                return
            dados_atualizar["senha_hash"] = nova_senha

        supabase.table("usuarios").update(dados_atualizar).eq("id", usuario_id).execute()

        # Atualiza a sessão pra sidebar refletir na hora
        st.session_state['nome_usuario'] = dados_atualizar["nome"]
        if "foto_base64" in dados_atualizar:
            st.session_state['foto_base64'] = dados_atualizar["foto_base64"]

        mostrar_popup("Perfil atualizado com sucesso!")
        st.rerun()

    # ==========================================================
    # TROCA DE E-MAIL (com confirmação por link, feita à parte
    # do formulário principal porque o e-mail é usado no login)
    # ==========================================================
    st.markdown("---")
    st.subheader("📧 Trocar e-mail de login")

    email_pendente = dados_usuario.get("novo_email_pendente")
    if email_pendente:
        st.info(f"⏳ Aguardando confirmação para: **{email_pendente}**. Verifique a caixa de entrada (e o spam) desse e-mail.")
        if st.button("Cancelar troca de e-mail pendente"):
            supabase.table("usuarios").update({
                "novo_email_pendente": None, "token_troca_email": None
            }).eq("id", usuario_id).execute()
            mostrar_popup("Troca de e-mail cancelada.")
            st.rerun()
    else:
        with st.form("form_trocar_email"):
            novo_email_desejado = st.text_input("Novo e-mail")
            enviar_confirmacao = st.form_submit_button("Enviar link de confirmação")

        if enviar_confirmacao:
            novo_email_desejado = novo_email_desejado.strip().lower()
            if not novo_email_desejado or not re.match(REGEX_EMAIL, novo_email_desejado):
                mostrar_popup("Informe um e-mail válido.", tipo="erro")
            elif novo_email_desejado == dados_usuario['email'].strip().lower():
                mostrar_popup("Esse já é o seu e-mail atual.", tipo="erro")
            else:
                email_existente = supabase.table("usuarios").select("id") \
                    .eq("email", novo_email_desejado).execute()
                if email_existente.data:
                    mostrar_popup("Já existe uma conta com esse e-mail.", tipo="erro")
                else:
                    token_troca = secrets.token_urlsafe(24)
                    supabase.table("usuarios").update({
                        "novo_email_pendente": novo_email_desejado,
                        "token_troca_email": token_troca
                    }).eq("id", usuario_id).execute()
                    if enviar_email_troca_confirmacao(novo_email_desejado, dados_usuario['nome'], token_troca):
                        mostrar_popup(f"Enviamos um link de confirmação para {novo_email_desejado}. Clique nele pra concluir a troca.")
                    st.rerun()
