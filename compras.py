"""
compras.py
Fornecedores e pedidos de compra. Restrito a Dono/Gerente/Admin.
"""
import streamlit as st
from datetime import date

from config import supabase
from utils import formatar_moeda, mostrar_popup
from auth import exigir_acesso_completo


def buscar_fornecedores():
    emp_id = st.session_state['empresa_id']
    resp = supabase.table("fornecedores").select("*").eq("empresa_id", emp_id).order("nome").execute()
    return resp.data or []


def tela_compras():
    exigir_acesso_completo()
    st.title("🛒 Compras")
    emp_id = st.session_state['empresa_id']
    usuario_id = st.session_state['usuario_id']

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
