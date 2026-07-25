"""
financeiro.py
Resumo financeiro por período: receita, despesas, compras, lucro líquido,
extrato editável de despesas e exportação em Excel. Restrito a Dono/Gerente/Admin.
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime, date

from config import supabase
from utils import formatar_moeda, mostrar_popup, parse_data_segura
from auth import exigir_acesso_completo


def tela_financeiro():
    exigir_acesso_completo()
    st.title("💰 Financeiro")
    emp_id = st.session_state['empresa_id']

    nomes_meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
                   "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    ano_atual = datetime.now().year

    st.markdown("#### 🗓️ Selecione o Período")
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        ano_selecionado = st.number_input("Ano", min_value=2020, max_value=2100, value=ano_atual, step=1, key="fin_ano")
    with col_p2:
        meses_selecionados_nomes = st.multiselect(
            "Mês (ou meses) — deixe vazio para o ano inteiro",
            nomes_meses, default=[nomes_meses[datetime.now().month - 1]], key="fin_meses"
        )
    meses_selecionados = [nomes_meses.index(m) + 1 for m in meses_selecionados_nomes] if meses_selecionados_nomes else list(range(1, 13))

    def _dentro_periodo(data_str):
        d = parse_data_segura(data_str)
        if not d:
            return False
        return d.year == ano_selecionado and d.month in meses_selecionados

    # ---- Receita (vendas concluídas) ----
    vendas_resp = supabase.table("vendas").select("id, valor_total, forma_pagamento, criado_em") \
        .eq("empresa_id", emp_id).eq("status", "concluida").execute()
    vendas_periodo = [v for v in (vendas_resp.data or []) if _dentro_periodo(v['criado_em'])]
    receita_total = sum(float(v['valor_total']) for v in vendas_periodo)
    qtd_vendas_periodo = len(vendas_periodo)
    ticket_medio = receita_total / qtd_vendas_periodo if qtd_vendas_periodo else 0.0

    receita_por_forma = {}
    for v in vendas_periodo:
        receita_por_forma[v['forma_pagamento']] = receita_por_forma.get(v['forma_pagamento'], 0.0) + float(v['valor_total'])

    # ---- Despesas operacionais avulsas ----
    despesas_resp = supabase.table("despesas").select("*").eq("empresa_id", emp_id).execute()
    despesas_periodo = [d for d in (despesas_resp.data or []) if _dentro_periodo(d.get('data_despesa'))]
    total_despesas = sum(float(d['valor']) for d in despesas_periodo)

    # ---- Compras de mercadoria já recebidas ----
    compras_resp = supabase.table("compras").select("*, fornecedores(nome)").eq("empresa_id", emp_id).eq("status", "chegou").execute()
    compras_periodo = [c for c in (compras_resp.data or []) if _dentro_periodo(c.get('data_chegada'))]
    total_compras = sum(float(c['valor_total'] or 0) for c in compras_periodo)

    lucro_liquido = receita_total - total_despesas - total_compras

    st.markdown(f"#### 📊 Resumo — {', '.join(meses_selecionados_nomes) if meses_selecionados_nomes else 'Ano inteiro'} de {ano_selecionado}")
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    col_r1.metric("💵 Receita (Vendas)", f"R$ {formatar_moeda(receita_total)}", help=f"{qtd_vendas_periodo} venda(s)")
    col_r2.metric("📦 Compras de Mercadoria", f"R$ {formatar_moeda(total_compras)}")
    col_r3.metric("📉 Despesas Operacionais", f"R$ {formatar_moeda(total_despesas)}")
    col_r4.metric("✨ Lucro Líquido", f"R$ {formatar_moeda(lucro_liquido)}",
                  delta="Positivo" if lucro_liquido >= 0 else "Atenção",
                  delta_color="normal" if lucro_liquido >= 0 else "inverse")
    st.caption(f"🎟️ Ticket médio por venda: R$ {formatar_moeda(ticket_medio)}")

    clientes_saldo_resp = supabase.table("clientes").select("saldo_devedor").eq("empresa_id", emp_id).execute()
    total_fiado_pendente = sum(float(c['saldo_devedor'] or 0) for c in (clientes_saldo_resp.data or []))
    if total_fiado_pendente > 0:
        st.info(f"💳 R$ {formatar_moeda(total_fiado_pendente)} em fiado pendente de recebimento no total (já contabilizado na receita, mas ainda não está fisicamente no caixa).")

    st.markdown("---")
    st.markdown("#### 💳 Vendas por Forma de Pagamento")
    if receita_por_forma:
        df_formas = pd.DataFrame([{"Forma": k.replace("_", " ").title(), "Valor": v} for k, v in receita_por_forma.items()])
        st.bar_chart(df_formas.set_index("Forma"))
    else:
        st.caption("Nenhuma venda registrada neste período.")

    st.markdown("---")
    with st.expander("➕ Registrar Despesa Operacional (aluguel, luz, água, salário...)", expanded=False):
        with st.form("form_despesa_operacional"):
            categoria_despesa = st.selectbox("Categoria", ["Aluguel", "Energia", "Água", "Salário", "Manutenção", "Fornecedor de Serviço", "Outros"])
            descricao_despesa = st.text_input("Descrição")
            valor_despesa = st.number_input("Valor (R$)", min_value=0.0, step=5.0, format="%.2f")
            data_despesa_input = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            registrar_despesa = st.form_submit_button("Registrar Despesa")
        if registrar_despesa:
            if valor_despesa <= 0:
                mostrar_popup("Informe um valor maior que zero.", tipo="erro")
            else:
                supabase.table("despesas").insert({
                    "empresa_id": emp_id, "categoria": categoria_despesa, "descricao": descricao_despesa,
                    "valor": valor_despesa, "data_despesa": str(data_despesa_input)
                }).execute()
                mostrar_popup("DESPESA REGISTRADA COM SUCESSO!")
                st.rerun()

    st.markdown("#### 📜 Extrato de Despesas Operacionais do Período")
    if despesas_periodo:
        df_desp_show = pd.DataFrame(despesas_periodo)[["data_despesa", "categoria", "descricao", "valor"]].copy()
        df_desp_show = df_desp_show.sort_values("data_despesa", ascending=False)
        df_desp_show["data_despesa"] = df_desp_show["data_despesa"].apply(
            lambda d: datetime.strptime(str(d).split("T")[0], "%Y-%m-%d").strftime("%d/%m/%Y")
        )
        st.dataframe(df_desp_show, use_container_width=True, hide_index=True)

        with st.expander("✏️ Editar ou Excluir uma Despesa", expanded=False):
            opcoes_desp = {
                f"{datetime.strptime(str(d['data_despesa']).split('T')[0], '%Y-%m-%d').strftime('%d/%m/%Y')} — {d['categoria']} — R$ {float(d['valor']):.2f}": d['id']
                for d in despesas_periodo
            }
            escolha_desp = st.selectbox("Selecione a despesa", list(opcoes_desp.keys()), key="select_edit_despesa")
            despesa_sel = next(d for d in despesas_periodo if d['id'] == opcoes_desp[escolha_desp])

            col_ed1, col_ed2 = st.columns(2)
            categorias_desp = ["Aluguel", "Energia", "Água", "Salário", "Manutenção", "Fornecedor de Serviço", "Outros"]
            with col_ed1:
                categoria_edit = st.selectbox(
                    "Categoria", categorias_desp,
                    index=(categorias_desp.index(despesa_sel['categoria']) if despesa_sel['categoria'] in categorias_desp else 0),
                    key="edit_categoria_desp_fin"
                )
            with col_ed2:
                valor_edit = st.number_input("Valor (R$)", min_value=0.0, value=float(despesa_sel['valor']), step=5.0, format="%.2f", key="edit_valor_desp_fin")
            descricao_edit = st.text_input("Descrição", value=despesa_sel.get('descricao') or "", key="edit_desc_desp_fin")
            data_edit = st.date_input(
                "Data", value=datetime.strptime(str(despesa_sel['data_despesa']).split("T")[0], "%Y-%m-%d").date(),
                format="DD/MM/YYYY", key="edit_data_desp_fin"
            )

            col_be1, col_be2 = st.columns(2)
            with col_be1:
                if st.button("💾 Salvar Alteração", key="btn_salvar_desp_fin"):
                    supabase.table("despesas").update({
                        "categoria": categoria_edit, "descricao": descricao_edit,
                        "valor": valor_edit, "data_despesa": str(data_edit)
                    }).eq("id", despesa_sel['id']).execute()
                    mostrar_popup("DESPESA ATUALIZADA COM SUCESSO!")
                    st.rerun()
            with col_be2:
                if st.button("🗑️ Excluir Despesa", key="btn_excluir_desp_fin"):
                    supabase.table("despesas").delete().eq("id", despesa_sel['id']).execute()
                    mostrar_popup("DESPESA EXCLUÍDA!")
                    st.rerun()
    else:
        st.caption("Nenhuma despesa operacional registrada neste período.")

    st.markdown("---")
    st.markdown("#### 📦 Compras de Mercadoria Recebidas no Período")
    if compras_periodo:
        df_compras_show = pd.DataFrame([{
            "Data Chegada": c.get('data_chegada'),
            "Fornecedor": c['fornecedores']['nome'] if c.get('fornecedores') else "-",
            "Nº Pedido": c.get('numero_pedido') or "-",
            "Valor Total": c.get('valor_total') or 0
        } for c in compras_periodo])
        st.dataframe(df_compras_show, use_container_width=True, hide_index=True)
    else:
        df_compras_show = pd.DataFrame()
        st.caption("Nenhuma compra recebida neste período.")

    st.markdown("---")
    st.markdown("#### 📤 Exportar Resumo do Período (Excel)")
    buffer_excel_fin = io.BytesIO()
    with pd.ExcelWriter(buffer_excel_fin, engine="openpyxl") as writer:
        pd.DataFrame([{
            "Período": f"{', '.join(meses_selecionados_nomes) if meses_selecionados_nomes else 'Ano inteiro'} de {ano_selecionado}",
            "Receita (Vendas)": receita_total, "Compras de Mercadoria": total_compras,
            "Despesas Operacionais": total_despesas, "Lucro Líquido": lucro_liquido,
            "Qtd Vendas": qtd_vendas_periodo, "Ticket Médio": ticket_medio
        }]).to_excel(writer, index=False, sheet_name="Resumo")
        if despesas_periodo:
            pd.DataFrame(despesas_periodo)[["data_despesa", "categoria", "descricao", "valor"]].to_excel(writer, index=False, sheet_name="Despesas")
        if compras_periodo and not df_compras_show.empty:
            df_compras_show.to_excel(writer, index=False, sheet_name="Compras Recebidas")
    buffer_excel_fin.seek(0)
    st.download_button(
        "📊 Baixar Excel do Período", data=buffer_excel_fin,
        file_name=f"financeiro_{ano_selecionado}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
