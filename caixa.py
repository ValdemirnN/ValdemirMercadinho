"""
caixa.py
Controle de caixa: abertura com escolha de TERMINAL, sangria, fechamento
"cego" para operadores (não vê diferença nem valor esperado), e histórico de
caixas — que para o Operador mostra somente os caixas que ele mesmo abriu, e
para Dono/Gerente/Admin mostra tudo com todos os detalhes.
"""
import streamlit as st
from datetime import datetime

from config import supabase
from utils import formatar_moeda, mostrar_popup, formatar_data_hora
from auth import pode_ver_diferenca_caixa, tem_acesso_completo


# ==============================================================
# CONSULTAS BÁSICAS
# ==============================================================
def buscar_caixa_aberto():
    """Retorna o caixa aberto do operador logado (se houver)."""
    emp_id = st.session_state['empresa_id']
    usuario_id = st.session_state['usuario_id']
    resultado = supabase.table("caixas").select("*").eq("empresa_id", emp_id) \
        .eq("operador_id", usuario_id).eq("status", "aberto").order("id", desc=True).limit(1).execute()
    return resultado.data[0] if resultado.data else None


def _terminal_em_uso(terminal, emp_id):
    """Verifica se um terminal já está com um caixa aberto por QUALQUER operador."""
    resultado = supabase.table("caixas").select("id, usuarios(nome)") \
        .eq("empresa_id", emp_id).eq("terminal", terminal).eq("status", "aberto").execute()
    return resultado.data[0] if resultado.data else None


def _listar_terminais_conhecidos(emp_id):
    resultado = supabase.table("caixas").select("terminal").eq("empresa_id", emp_id).execute()
    terminais = sorted({t['terminal'] for t in (resultado.data or []) if t.get('terminal')})
    return terminais


# ==============================================================
# ABERTURA DE CAIXA (COM ESCOLHA DE TERMINAL)
# ==============================================================
def tela_abrir_caixa():
    st.title("🔒 Abertura de Caixa")
    emp_id = st.session_state['empresa_id']
    usuario_id = st.session_state['usuario_id']

    st.info("Escolha o terminal físico em que você vai trabalhar e informe o troco inicial da gaveta.")

    terminais_conhecidos = _listar_terminais_conhecidos(emp_id)
    if not terminais_conhecidos:
        terminais_conhecidos = ["Caixa 01", "Caixa 02"]

    modo_terminal = st.radio(
        "Terminal", ["Selecionar terminal existente", "Cadastrar novo terminal"],
        horizontal=True, key="modo_terminal_abertura"
    )
    if modo_terminal == "Selecionar terminal existente":
        terminal_escolhido = st.selectbox("Qual terminal?", terminais_conhecidos, key="select_terminal_abertura")
    else:
        terminal_escolhido = st.text_input("Nome do novo terminal", placeholder="Ex: Caixa 03", key="novo_terminal_abertura")

    with st.form("form_abrir_caixa"):
        valor_abertura = st.number_input("Valor inicial na gaveta (troco)", min_value=0.0, step=5.0, value=0.0, format="%.2f")
        abrir = st.form_submit_button("🔓 Abrir Caixa")

    if abrir:
        terminal_final = (terminal_escolhido or "").strip()
        if not terminal_final:
            mostrar_popup("Informe o terminal em que você vai trabalhar.", tipo="erro")
            return

        # Regra 1: o operador não pode ter dois caixas abertos ao mesmo tempo.
        caixa_proprio_aberto = buscar_caixa_aberto()
        if caixa_proprio_aberto:
            mostrar_popup(
                f"Você já tem um caixa aberto no terminal '{caixa_proprio_aberto.get('terminal', '-')}'. "
                f"Feche-o antes de abrir outro.", tipo="erro"
            )
            return

        # Regra 2: o terminal escolhido não pode estar em uso por outro operador.
        caixa_terminal_em_uso = _terminal_em_uso(terminal_final, emp_id)
        if caixa_terminal_em_uso:
            nome_ocupante = caixa_terminal_em_uso.get('usuarios', {}).get('nome') if caixa_terminal_em_uso.get('usuarios') else "outro operador"
            mostrar_popup(f"O terminal '{terminal_final}' já está em uso por {nome_ocupante}. Escolha outro terminal.", tipo="erro")
            return

        supabase.table("caixas").insert({
            "empresa_id": emp_id,
            "operador_id": usuario_id,
            "terminal": terminal_final,
            "valor_abertura": valor_abertura,
            "status": "aberto"
        }).execute()
        mostrar_popup(f"CAIXA ABERTO COM SUCESSO NO TERMINAL '{terminal_final}'!")
        st.rerun()


# ==============================================================
# TOTAIS DO CAIXA
# ==============================================================
def calcular_totais_caixa(caixa):
    vendas_caixa = supabase.table("vendas").select("valor_total, forma_pagamento, status") \
        .eq("caixa_id", caixa['id']).eq("status", "concluida").execute()
    total_dinheiro = sum(float(v['valor_total']) for v in (vendas_caixa.data or []) if v['forma_pagamento'] == 'dinheiro')
    total_geral = sum(float(v['valor_total']) for v in (vendas_caixa.data or []))
    qtd_vendas = len(vendas_caixa.data or [])

    sangrias = supabase.table("sangrias_caixa").select("valor").eq("caixa_id", caixa['id']).execute()
    total_sangrias = sum(float(s['valor']) for s in (sangrias.data or []))

    valor_esperado_gaveta = float(caixa['valor_abertura']) + total_dinheiro - total_sangrias
    return {
        "total_dinheiro": total_dinheiro, "total_geral": total_geral, "qtd_vendas": qtd_vendas,
        "total_sangrias": total_sangrias, "valor_esperado_gaveta": valor_esperado_gaveta
    }


# ==============================================================
# WIDGET DE STATUS DO CAIXA (SIDEBAR) — fechamento "cego" para operador
# ==============================================================
def widget_status_caixa(caixa):
    pode_ver_diferenca = pode_ver_diferenca_caixa()

    with st.sidebar.expander(f"💵 Caixa Aberto — {caixa.get('terminal', 'Terminal')}", expanded=False):
        totais = calcular_totais_caixa(caixa)
        st.write(f"Abertura: R$ {formatar_moeda(caixa['valor_abertura'])}")
        st.write(f"Vendas: {totais['qtd_vendas']} (R$ {formatar_moeda(totais['total_geral'])})")

        # Sobra/falta e valor esperado só aparecem para quem tem acesso completo.
        if pode_ver_diferenca:
            st.write(f"Sangrias: R$ {formatar_moeda(totais['total_sangrias'])}")
            st.write(f"**Esperado na gaveta: R$ {formatar_moeda(totais['valor_esperado_gaveta'])}**")

        st.markdown("---")
        st.caption("Registrar sangria (retirada de dinheiro)")
        valor_sangria = st.number_input("Valor", min_value=0.0, step=5.0, format="%.2f", key="valor_sangria_sidebar")
        motivo_sangria = st.text_input("Motivo", key="motivo_sangria_sidebar")
        if st.button("Registrar Sangria", key="btn_sangria_sidebar"):
            if valor_sangria > 0 and motivo_sangria.strip():
                supabase.table("sangrias_caixa").insert({
                    "caixa_id": caixa['id'], "valor": valor_sangria, "motivo": motivo_sangria
                }).execute()
                mostrar_popup("SANGRIA REGISTRADA!")
                st.rerun()
            else:
                mostrar_popup("Informe valor e motivo.", tipo="erro")

        st.markdown("---")
        st.caption("Fechar caixa")
        if pode_ver_diferenca:
            st.caption("Informe o valor contado na gaveta para fechar o caixa.")
        else:
            st.caption("Conte o dinheiro da gaveta e informe o valor abaixo. A conferência será feita pelo gestor.")

        valor_fechamento_informado = st.number_input(
            "Valor contado na gaveta", min_value=0.0, step=5.0, format="%.2f", key="valor_fechamento_sidebar"
        )
        if st.button("🔒 Fechar Caixa", key="btn_fechar_caixa_sidebar"):
            diferenca = valor_fechamento_informado - totais['valor_esperado_gaveta']
            # O sistema SEMPRE calcula e grava a diferença e o valor esperado —
            # apenas não os exibe ao operador. Fica disponível no histórico
            # para quem tem acesso completo.
            supabase.table("caixas").update({
                "status": "fechado",
                "valor_fechamento_informado": valor_fechamento_informado,
                "valor_fechamento_calculado": totais['valor_esperado_gaveta'],
                "diferenca": diferenca,
                "data_fechamento": datetime.now().isoformat()
            }).eq("id", caixa['id']).execute()

            if pode_ver_diferenca:
                if abs(diferenca) < 0.01:
                    mostrar_popup("CAIXA FECHADO! Bateu certinho. 🎉")
                elif diferenca > 0:
                    mostrar_popup(f"Caixa fechado. Sobrou R$ {formatar_moeda(diferenca)} a mais na gaveta.")
                else:
                    mostrar_popup(f"Caixa fechado. Faltou R$ {formatar_moeda(abs(diferenca))} na gaveta.", tipo="erro")
            else:
                # Fechamento cego: o operador não sabe se sobrou/faltou.
                mostrar_popup("CAIXA FECHADO! Valor registrado com sucesso. A conferência será feita pelo gestor.")
            st.rerun()


# ==============================================================
# HISTÓRICO DE CAIXAS
# ==============================================================
def tela_historico_caixas():
    emp_id = st.session_state['empresa_id']
    usuario_id = st.session_state['usuario_id']
    pode_ver_diferenca = pode_ver_diferenca_caixa()

    st.title("📜 Histórico de Caixas")

    consulta = supabase.table("caixas").select("*, usuarios(nome)").eq("empresa_id", emp_id)
    if not tem_acesso_completo():
        consulta = consulta.eq("operador_id", usuario_id)
        st.caption("Exibindo apenas os caixas que você abriu.")
    else:
        st.caption("Todos os caixas abertos e fechados: quem operou, quanto entrou e o lucro estimado.")

    caixas_resp = consulta.order("id", desc=True).execute()
    lista_caixas = caixas_resp.data or []

    if not lista_caixas:
        st.info("Nenhum caixa registrado ainda.")
        return

    for caixa in lista_caixas:
        nome_operador = caixa['usuarios']['nome'] if caixa.get('usuarios') else "Operador desconhecido"
        status_aberto = caixa['status'] == 'aberto'
        icone_status = "🟢 Aberto" if status_aberto else "🔴 Fechado"
        terminal_txt = caixa.get('terminal') or "-"

        vendas_caixa_resp = supabase.table("vendas").select("id, valor_total, forma_pagamento") \
            .eq("caixa_id", caixa['id']).eq("status", "concluida").execute()
        vendas_caixa = vendas_caixa_resp.data or []
        total_vendido = sum(float(v['valor_total']) for v in vendas_caixa)
        qtd_vendas = len(vendas_caixa)

        titulo = (f"{icone_status} — 🖥️ {terminal_txt} — 👤 {nome_operador} — "
                  f"Abertura R$ {formatar_moeda(caixa['valor_abertura'])} — Vendeu R$ {formatar_moeda(total_vendido)}")

        with st.expander(titulo):
            if pode_ver_diferenca:
                # ---- Lucro estimado: receita - custo dos produtos vendidos ----
                ids_vendas_caixa = [v['id'] for v in vendas_caixa]
                custo_total = 0.0
                if ids_vendas_caixa:
                    itens_resp = supabase.table("itens_venda").select("quantidade, produtos(preco_custo)") \
                        .in_("venda_id", ids_vendas_caixa).execute()
                    for it in (itens_resp.data or []):
                        preco_custo_it = float(it['produtos']['preco_custo']) if it.get('produtos') and it['produtos'].get('preco_custo') else 0.0
                        custo_total += float(it['quantidade']) * preco_custo_it
                lucro_caixa = total_vendido - custo_total

                sangrias_resp = supabase.table("sangrias_caixa").select("valor").eq("caixa_id", caixa['id']).execute()
                total_sangrias = sum(float(s['valor']) for s in (sangrias_resp.data or []))
                valor_abertura = float(caixa['valor_abertura'])
                total_dinheiro = sum(float(v['valor_total']) for v in vendas_caixa if v['forma_pagamento'] == 'dinheiro')
                valor_esperado_gaveta = valor_abertura + total_dinheiro - total_sangrias

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("👤 Operador", nome_operador)
                col2.metric("💰 Abertura", f"R$ {formatar_moeda(valor_abertura)}")
                col3.metric("🛒 Vendas", f"{qtd_vendas}", help=f"Total vendido: R$ {formatar_moeda(total_vendido)}")
                col4.metric("✨ Lucro Estimado", f"R$ {formatar_moeda(lucro_caixa)}")
                col5.metric("📤 Sangrias", f"R$ {formatar_moeda(total_sangrias)}")

                if status_aberto:
                    st.info(f"💵 Esperado na gaveta agora: R$ {formatar_moeda(valor_esperado_gaveta)}")
                else:
                    col_f1, col_f2, col_f3 = st.columns(3)
                    col_f1.metric("🧮 Esperado no Fechamento", f"R$ {formatar_moeda(caixa.get('valor_fechamento_calculado') or 0)}")
                    col_f2.metric("🔢 Contado no Fechamento", f"R$ {formatar_moeda(caixa.get('valor_fechamento_informado') or 0)}")
                    diferenca = float(caixa.get('diferenca') or 0)
                    col_f3.metric(
                        "⚖️ Diferença", f"R$ {formatar_moeda(diferenca)}",
                        delta="Bateu certinho" if abs(diferenca) < 0.01 else ("Sobrou" if diferenca > 0 else "Faltou"),
                        delta_color="normal" if diferenca >= 0 else "inverse"
                    )
                    if caixa.get('data_fechamento'):
                        try:
                            dt_fech = datetime.fromisoformat(caixa['data_fechamento'].replace("Z", "+00:00"))
                            st.caption(f"🗓️ Fechado em: {dt_fech.strftime('%d/%m/%Y %H:%M')}")
                        except Exception:
                            pass
            else:
                # Visão restrita do Operador: sem lucro, sem sangrias, sem diferença/expectativa.
                col1, col2, col3 = st.columns(3)
                col1.metric("🖥️ Terminal", terminal_txt)
                col2.metric("💰 Abertura", f"R$ {formatar_moeda(caixa['valor_abertura'])}")
                col3.metric("🛒 Vendas", f"{qtd_vendas}", help=f"Total vendido: R$ {formatar_moeda(total_vendido)}")
                if status_aberto:
                    st.caption("Caixa em aberto.")
                else:
                    st.caption("🔒 Caixa fechado. A conferência de valores é feita pelo gestor.")
                    if caixa.get('data_fechamento'):
                        try:
                            dt_fech = datetime.fromisoformat(caixa['data_fechamento'].replace("Z", "+00:00"))
                            st.caption(f"🗓️ Fechado em: {dt_fech.strftime('%d/%m/%Y %H:%M')}")
                        except Exception:
                            pass

            if vendas_caixa:
                st.markdown("---")
                st.caption("💳 Vendas por forma de pagamento:")
                forma_totais = {}
                for v in vendas_caixa:
                    forma_totais[v['forma_pagamento']] = forma_totais.get(v['forma_pagamento'], 0.0) + float(v['valor_total'])
                for forma, val in forma_totais.items():
                    st.write(f"- {forma.replace('_', ' ').title()}: R$ {formatar_moeda(val)}")
            else:
                st.caption("Nenhuma venda registrada neste caixa.")
