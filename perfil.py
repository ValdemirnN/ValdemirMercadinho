"""
perfil.py
Tela "Meu Perfil": qualquer usuário logado (Dono, Gerente ou Operador) pode
ver e editar os próprios dados — nome, foto e senha. A foto é opcional; se
não for definida, mostra um ícone padrão. A foto é salva como base64 direto
na coluna usuarios.foto_base64 (não depende de bucket de Storage).
"""
import base64
import io

import streamlit as st

from config import supabase
from utils import mostrar_popup

TAMANHO_MAX_FOTO = (300, 300)  # redimensiona pra não pesar no banco


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
        "nome, email, cargo, perfil, foto_base64"
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
        st.caption("O e-mail de login e o cargo só podem ser alterados pelo Dono/Gerente, na aba Equipe.")

    st.markdown("---")
    st.subheader("✏️ Editar meus dados")

    with st.form("form_editar_perfil"):
        novo_nome = st.text_input("Nome", value=dados_usuario['nome'])
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

        dados_atualizar = {"nome": novo_nome.strip()}

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
