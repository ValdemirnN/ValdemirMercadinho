"""
admin.py
Painel restrito ao administrador do sistema (admin_geral): visão de todos os
mercadinhos assinantes, bloqueio/desbloqueio, troca de senha e renovação de
assinatura.
"""
import streamlit as st
from datetime import datetime
from dateutil.relativedelta import relativedelta

from config import supabase
from utils import mostrar_popup
from auth import ativar_conta_apos_pagamento


def tela_gestao_assinantes():
    st.title("👑 Gestão de Assinantes")
    st.caption("Painel restrito ao administrador do sistema (visão de todos os mercadinhos assinantes).")

    usuarios_resp = supabase.table("usuarios").select(
        "id, nome, email, ativo, senha_hash, email_confirmado, metodo_pagamento, comprovante_pagamento, empresa_id, perfil, empresas(nome_fantasia)"
    ).eq("perfil", "dono").execute()
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
