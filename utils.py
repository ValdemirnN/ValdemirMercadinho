"""
utils.py
Pequenas funções utilitárias usadas em vários módulos: formatação de moeda,
popups de aviso e parsing seguro de datas.
"""
import base64
import io
import re
import streamlit as st
from datetime import datetime

REQUISITOS_SENHA_TEXTO = (
    "A senha precisa ter: mínimo 7 caracteres, "
    "1 letra maiúscula, 1 número e 1 caractere especial (ex: !@#$%)."
)

TAMANHO_MAX_FOTO_PADRAO = (300, 300)


def processar_foto_upload(arquivo_upload, tamanho_max=TAMANHO_MAX_FOTO_PADRAO):
    """Recebe um arquivo do st.file_uploader, redimensiona e retorna base64 (str) pronto pra salvar."""
    try:
        from PIL import Image
    except ImportError:
        mostrar_popup("Biblioteca Pillow não instalada. Adicione 'Pillow' ao requirements.txt.", tipo="erro")
        return None

    try:
        imagem = Image.open(arquivo_upload)
        imagem = imagem.convert("RGB")
        imagem.thumbnail(tamanho_max)
        buffer = io.BytesIO()
        imagem.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        mostrar_popup(f"Não foi possível processar a imagem: {e}", tipo="erro")
        return None

REQUISITOS_SENHA_TEXTO = (
    "A senha precisa ter: mínimo 7 caracteres, "
    "1 letra maiúscula, 1 número e 1 caractere especial (ex: !@#$%)."
)


def validar_senha_forte(senha):
    """Retorna (True, '') se a senha atende aos requisitos, ou (False, 'mensagem do que falta')."""
    if len(senha) < 7:
        return False, "A senha precisa ter no mínimo 7 caracteres."
    if not re.search(r"[A-Z]", senha):
        return False, "A senha precisa ter pelo menos uma letra maiúscula."
    if not re.search(r"[0-9]", senha):
        return False, "A senha precisa ter pelo menos um número."
    if not re.search(r"[^A-Za-z0-9]", senha):
        return False, "A senha precisa ter pelo menos um caractere especial (ex: ! @ # $ % &)."
    return True, ""


def formatar_moeda(valor):
    if valor is None:
        return "0,00"
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mostrar_popup(mensagem, tipo="sucesso"):
    if tipo == "erro":
        st.error(f"⚠️ {mensagem}")
    else:
        st.success(f"✅ {mensagem}")


def parse_data_segura(data_str, formato="%Y-%m-%d"):
    """Faz parse de uma data em string, retornando None se falhar."""
    if not data_str:
        return None
    try:
        return datetime.strptime(str(data_str).split("T")[0], formato).date()
    except Exception:
        return None


def formatar_data_hora(iso_str):
    try:
        return datetime.fromisoformat(str(iso_str).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_str
