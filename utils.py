"""
utils.py
Pequenas funções utilitárias usadas em vários módulos: formatação de moeda,
popups de aviso e parsing seguro de datas.
"""
import streamlit as st
from datetime import datetime


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
