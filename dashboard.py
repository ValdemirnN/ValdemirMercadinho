"""
dashboard.py
Visão geral do negócio: KPIs do mês, alertas, evolução diária de vendas,
top produtos, próximos pedidos e o novo ranking "Funcionário do Mês".
Restrito a Dono/Gerente/Admin.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

from config import supabase
from utils import formatar_moeda, parse_data_segura
from auth import exigir_acesso_completo


def _secao_funcionario_do_mes(emp_id, hoje):
    st.markdown("---")
    st.subheader("🏆 Funcionário do Mês")
    st.caption("Ranking de vendas do time no mês vigente — total vendido e quantidade de vendas por operador.")

    vendas_resp = supabase.table("vendas").select("valor_total, operador_id, criado_em") \
        .eq("empresa_id", emp_id).eq("status", "concluida").execute()
    vendas_mes = [
        v for v in (vendas_resp.data or [])
        if (d := parse_data_segura(v['criado_em'])) and d.year == hoje.year and d.month == hoje.month
    ]

    if not vendas_mes:
        st.info("Nenhuma venda registrada neste mês ainda para gerar o ranking.")
        return

    usuarios_resp = supabase.table("usuarios").select("id, nome").eq("empresa_id", emp_id).execute()
    mapa_nomes = {u['id']: u['nome'] for u in (usuarios_resp.data or [])}

    desempenho = {}
    for v in vendas_mes:
        oid = v.get('operador_id')
        if oid is None:
            continue
        if oid not in desempenho:
            desempenho[oid] = {"total": 0.0, "qtd": 0}
        desempenho[oid]['total'] += float(v['valor_total'])
        desempenho[oid]['qtd'] += 1

    ranking = sorted(desempenho.items(), key=lambda item: item[1]['total'], reverse=True)

    if not ranking:
        st.info("Nenhuma venda com operador identificado neste mês ainda.")
        return

    # ---- Pódio (top 3) ----
    medalhas = ["🥇", "🥈", "🥉"]
    top3 = ranking[:3]
    cols_podio = st.columns(len(top3))
    for idx, (oid, dados) in enumerate(top3):
        nome_op = mapa_nomes.get(oid, "Operador")
        with cols_podio[idx]:
            st.metric(
                f"{medalhas[idx]} {nome_op}",
                f"R$ {formatar_moeda(dados['total'])}",
                help=f"{dados['qtd']} venda(s) no mês"
            )

    # ---- Gráfico comparativo do time inteiro ----
    df_ranking = pd.DataFrame([
        {"Operador": mapa_nomes.get(oid, f"Usuário #{oid}"), "Total Vendido": dados['total'], "Vendas": dados['qtd']}
        for oid, dados in ranking
    ])
    fig_ranking = px.bar(
        df_ranking.sort_values("Total Vendido", ascending=True),
        x="Total Vendido", y="Operador", orientation="h",
        template="plotly_dark", color_discrete_sequence=["#3B82F6"],
        hover_data={"Vendas": True}
    )
    fig_ranking.update_layout(showlegend=False, margin=dict(t=10, b=0, l=0, r=0), xaxis=dict(title="Total Vendido (R$)"), yaxis=dict(title=""))
    st.plotly_chart(fig_ranking, use_container_width=True)


def tela_dashboard():
    exigir_acesso_completo()
    emp_id = st.session_state['empresa_id']
    nome_usuario = st.session_state['nome_usuario']

    st.title("📊 Dashboard")
    st.markdown(f"### 👋 Bem-vindo, {nome_usuario}!")
    st.markdown("---")

    hoje = date.today()

    def _no_mes_atual(data_str):
        d = parse_data_segura(data_str)
        return bool(d) and d.year == hoje.year and d.month == hoje.month

    def _hoje(data_str):
        d = parse_data_segura(data_str)
        return d == hoje

    # ---- Vendas do mês ----
    vendas_resp = supabase.table("vendas").select("id, valor_total, criado_em") \
        .eq("empresa_id", emp_id).eq("status", "concluida").execute()
    vendas_mes = [v for v in (vendas_resp.data or []) if _no_mes_atual(v['criado_em'])]
    vendas_hoje = [v for v in vendas_mes if _hoje(v['criado_em'])]

    receita_mes = sum(float(v['valor_total']) for v in vendas_mes)
    qtd_vendas_mes = len(vendas_mes)
    ticket_medio_mes = receita_mes / qtd_vendas_mes if qtd_vendas_mes else 0.0
    receita_hoje = sum(float(v['valor_total']) for v in vendas_hoje)

    # ---- Despesas e compras do mês ----
    despesas_resp = supabase.table("despesas").select("valor, data_despesa").eq("empresa_id", emp_id).execute()
    despesas_mes = sum(float(d['valor']) for d in (despesas_resp.data or []) if _no_mes_atual(d.get('data_despesa')))

    compras_resp = supabase.table("compras").select("valor_total, data_chegada, status").eq("empresa_id", emp_id).eq("status", "chegou").execute()
    compras_mes = sum(float(c['valor_total'] or 0) for c in (compras_resp.data or []) if _no_mes_atual(c.get('data_chegada')))

    lucro_mes = receita_mes - despesas_mes - compras_mes

    # ---- KPIs principais ----
    col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
    col_k1.metric("💰 Receita do Mês", f"R$ {formatar_moeda(receita_mes)}")
    col_k2.metric("✨ Lucro do Mês", f"R$ {formatar_moeda(lucro_mes)}", delta="Positivo" if lucro_mes >= 0 else "Atenção", delta_color="normal" if lucro_mes >= 0 else "inverse")
    col_k3.metric("🎟️ Ticket Médio", f"R$ {formatar_moeda(ticket_medio_mes)}")
    col_k4.metric("🛒 Vendas Hoje", len(vendas_hoje), delta=f"R$ {formatar_moeda(receita_hoje)}")
    col_k5.metric("📅 Vendas no Mês", qtd_vendas_mes)

    st.markdown("---")

    # ---- Painel de alertas ----
    produtos_resp = supabase.table("produtos").select("id, nome, estoque_atual, estoque_minimo, data_validade").eq("empresa_id", emp_id).eq("ativo", True).execute()
    produtos_ativos = produtos_resp.data or []
    qtd_estoque_baixo = len([p for p in produtos_ativos if float(p['estoque_atual'] or 0) <= float(p['estoque_minimo'] or 0)])
    produtos_vencendo = [
        p for p in produtos_ativos
        if p.get('data_validade') and (d := parse_data_segura(p['data_validade'])) and 0 <= (d - hoje).days <= 7
    ]

    clientes_saldo_resp = supabase.table("clientes").select("saldo_devedor").eq("empresa_id", emp_id).execute()
    total_fiado_pendente = sum(float(c['saldo_devedor'] or 0) for c in (clientes_saldo_resp.data or []))

    pedidos_aguardando_resp = supabase.table("compras").select("id").eq("empresa_id", emp_id).eq("status", "aguardando").execute()
    qtd_pedidos_aguardando = len(pedidos_aguardando_resp.data or [])

    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    col_a1.metric("🟡 Estoque Baixo", qtd_estoque_baixo)
    col_a2.metric("🟠 Vencendo em 7 dias", len(produtos_vencendo))
    col_a3.metric("💳 Fiado a Receber", f"R$ {formatar_moeda(total_fiado_pendente)}")
    col_a4.metric("📦 Pedidos Aguardando", qtd_pedidos_aguardando)

    if produtos_vencendo:
        with st.expander(f"🟠 Ver os {len(produtos_vencendo)} produto(s) vencendo em breve"):
            for p in produtos_vencendo:
                d_val = parse_data_segura(p['data_validade'])
                dias_rest = (d_val - hoje).days
                st.write(f"- **{p['nome']}** — vence em {dias_rest} dia(s)")

    st.markdown("---")

    # ---- Evolução diária de vendas no mês ----
    col_g1, col_g2 = st.columns([1.6, 1])

    with col_g1:
        st.subheader("📈 Vendas Diárias do Mês")
        if vendas_mes:
            df_vendas_mes = pd.DataFrame(vendas_mes)
            df_vendas_mes['Data'] = pd.to_datetime(df_vendas_mes['criado_em'].str.split("T").str[0])
            df_diario = df_vendas_mes.groupby('Data')['valor_total'].sum().reset_index()
            df_diario.columns = ['Data', 'Receita']
            df_diario['Receita'] = df_diario['Receita'].astype(float)

            fig_evolucao = px.area(df_diario, x="Data", y="Receita", template="plotly_dark")
            fig_evolucao.update_traces(line_color="#FFC107", fillcolor="rgba(255,193,7,0.2)")
            fig_evolucao.update_layout(margin=dict(t=20, b=0, l=0, r=0), yaxis=dict(title=""), xaxis=dict(title=""))
            st.plotly_chart(fig_evolucao, use_container_width=True)
        else:
            st.info("Nenhuma venda registrada neste mês ainda.")

    with col_g2:
        st.subheader("🏆 Top 5 Produtos (mês)")
        ids_vendas_mes = [v['id'] for v in vendas_mes]

        if ids_vendas_mes:
            itens_venda_resp = supabase.table("itens_venda").select("produto_id, quantidade").in_("venda_id", ids_vendas_mes).execute()
            itens_mes = itens_venda_resp.data or []
        else:
            itens_mes = []

        if itens_mes:
            mapa_nomes_prod = {p['id']: p['nome'] for p in produtos_ativos}
            uso_produtos = {}
            for it in itens_mes:
                pid = it['produto_id']
                uso_produtos[pid] = uso_produtos.get(pid, 0) + float(it['quantidade'])

            df_top = pd.DataFrame([
                {"Produto": mapa_nomes_prod.get(pid, f"Produto #{pid}"), "Qtd": qtd}
                for pid, qtd in uso_produtos.items()
            ]).sort_values("Qtd", ascending=True).tail(5)

            fig_top = px.bar(df_top, x="Qtd", y="Produto", orientation='h', template="plotly_dark", color_discrete_sequence=["#FFC107"])
            fig_top.update_layout(showlegend=False, margin=dict(t=10, b=0, l=0, r=0), xaxis=dict(title="", showticklabels=False), yaxis=dict(title=""))
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.info("Sem vendas suficientes para ranking ainda.")

    st.markdown("---")
    st.subheader("📦 Próximos Pedidos Aguardando Chegada")
    pedidos_prox_resp = supabase.table("compras").select("id, numero_pedido, valor_total, data_prevista_chegada, fornecedores(nome)") \
        .eq("empresa_id", emp_id).eq("status", "aguardando").order("data_prevista_chegada").limit(5).execute()
    if pedidos_prox_resp.data:
        for pedido in pedidos_prox_resp.data:
            nome_forn = pedido['fornecedores']['nome'] if pedido.get('fornecedores') else "Fornecedor não informado"
            st.write(f"⏳ **{pedido.get('data_prevista_chegada') or '-'}** — {nome_forn} — R$ {formatar_moeda(pedido['valor_total'])}")
    else:
        st.caption("Nenhum pedido aguardando chegada no momento.")

    # ---- NOVO: Ranking Funcionário do Mês ----
    _secao_funcionario_do_mes(emp_id, hoje)
