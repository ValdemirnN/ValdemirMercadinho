"""
fiado.py
Controle de clientes fiado: cadastro, histórico de compras/pagamentos e
registro de pagamento. Acessível a todos os perfis (Operador também usa).
"""
import streamlit as st
from datetime import datetime

from config import supabase
from utils import formatar_moeda, mostrar_popup, formatar_data_hora


def tela_fiado():
    st.title("💳 Fiado - Controle de Clientes")
    emp_id = st.session_state['empresa_id']
    usuario_id = st.session_state['usuario_id']

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
                            st.write(f"🧾 {formatar_data_hora(v['criado_em'])} — R$ {formatar_moeda(v['valor_total'])}")
                    else:
                        st.caption("Nenhuma compra fiado registrada.")

                    st.markdown("---")
                    st.caption("Pagamentos realizados:")
                    pagamentos = supabase.table("pagamentos_fiado").select("valor, forma_pagamento, criado_em, observacao") \
                        .eq("cliente_id", cliente['id']).order("criado_em", desc=True).execute()
                    if pagamentos.data:
                        for p in pagamentos.data:
                            obs_p = f" — {p['observacao']}" if p.get('observacao') else ""
                            st.write(f"💵 {formatar_data_hora(p['criado_em'])} — R$ {formatar_moeda(p['valor'])} ({p['forma_pagamento']}){obs_p}")
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
