"""
pdv.py
Ponto de Venda: busca por código de barras ou nome, carrinho, formas de
pagamento (incluindo fiado) e finalização da venda. Acessível a todos os
perfis (é a tela principal do Operador).
"""
import streamlit as st

from config import supabase
from utils import formatar_moeda, mostrar_popup


def tela_pdv(caixa):
    st.title("🧾 Ponto de Venda")
    from caixa import widget_status_caixa
    widget_status_caixa(caixa)

    emp_id = st.session_state['empresa_id']
    usuario_id = st.session_state['usuario_id']

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
