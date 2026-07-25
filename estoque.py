"""
estoque.py
Gestão de estoque: listagem/edição de produtos, cadastro, categorias e ajuste
manual de estoque. Restrito a Dono/Gerente/Admin (o app.py só mostra este
menu para quem tem acesso completo, e a função também se protege sozinha).
"""
import streamlit as st
from datetime import datetime, date

from config import supabase
from utils import formatar_moeda, mostrar_popup
from auth import exigir_acesso_completo


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
    emp_id = st.session_state['empresa_id']
    resp = supabase.table("categorias").select("id, nome").eq("empresa_id", emp_id).order("nome").execute()
    return resp.data or []


def tela_estoque():
    exigir_acesso_completo()
    st.title("📦 Estoque")
    emp_id = st.session_state['empresa_id']
    usuario_id = st.session_state['usuario_id']

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
