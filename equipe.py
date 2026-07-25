"""
equipe.py
Gestão de equipe: o Dono/Gerente cadastra Operadores (e outros Gerentes) que
vão trabalhar no PDV. Sem essa tela não existe forma de criar usuários com
perfil "operador", então ela é o que viabiliza a visão segmentada por perfil.

Somente Dono e Gerente enxergam esta aba (Operador não vê, Admin_geral não
precisa pois ele gerencia assinantes, não equipe de mercadinho).
"""
import streamlit as st

from config import supabase
from utils import mostrar_popup
from auth import exigir_acesso_completo, MODULOS_EXTRAS_DISPONIVEIS


PERFIS_CRIAVEIS = {"Operador (PDV apenas, por padrão)": "operador", "Gerente (acesso completo)": "gerente"}

# Cargos são só um rótulo de identificação (aparece no cadastro/listagem).
# Quem manda no que a pessoa acessa é o perfil + as permissões extras abaixo.
CARGOS_OPERADOR = ["Caixa", "Secretário(a)", "Repositor(a)", "Estoquista"]
CARGOS_GERENTE = ["Gerente"]


def tela_equipe():
    exigir_acesso_completo()
    st.title("👥 Equipe")
    emp_id = st.session_state['empresa_id']

    tab_lista, tab_cad = st.tabs(["📋 Membros da Equipe", "➕ Cadastrar Membro"])

    with tab_cad:
        st.caption("Por padrão, Operadores só acessam o PDV e só veem o histórico dos próprios caixas (sem ver diferenças de fechamento). Marque abaixo quais outras páginas esse membro pode acessar.")
        with st.form("form_cadastro_equipe"):
            nome_membro = st.text_input("Nome")
            email_membro = st.text_input("E-mail (usado para login)")
            senha_membro = st.text_input("Senha inicial", type="password")
            perfil_escolhido_label = st.selectbox("Perfil", list(PERFIS_CRIAVEIS.keys()))
            perfil_escolhido = PERFIS_CRIAVEIS[perfil_escolhido_label]

            lista_cargos = CARGOS_OPERADOR if perfil_escolhido == "operador" else CARGOS_GERENTE
            cargo_escolhido = st.selectbox("Cargo (rótulo de identificação)", lista_cargos)

            modulos_marcados = []
            if perfil_escolhido == "operador":
                st.markdown("**Páginas que esse Operador pode acessar (além do PDV):**")
                for chave_modulo, label_modulo in MODULOS_EXTRAS_DISPONIVEIS:
                    if st.checkbox(label_modulo, key=f"novo_membro_modulo_{chave_modulo}"):
                        modulos_marcados.append(chave_modulo)
            else:
                st.info("Gerente já acessa todas as páginas do sistema automaticamente.")

            cadastrar = st.form_submit_button("Cadastrar Membro")

        if cadastrar:
            if not nome_membro.strip() or not email_membro.strip():
                mostrar_popup("Preencha nome e e-mail.", tipo="erro")
            elif len(senha_membro) < 7:
                mostrar_popup("A senha precisa ter no mínimo 7 caracteres.", tipo="erro")
            else:
                email_existente = supabase.table("usuarios").select("id").eq("email", email_membro.strip()).execute()
                if email_existente.data:
                    mostrar_popup("Já existe uma conta com esse e-mail.", tipo="erro")
                else:
                    supabase.table("usuarios").insert({
                        "empresa_id": emp_id,
                        "nome": nome_membro.strip(),
                        "email": email_membro.strip(),
                        "senha_hash": senha_membro,
                        "perfil": perfil_escolhido,
                        "cargo": cargo_escolhido,
                        "permissoes_extras": modulos_marcados,
                        "ativo": True,
                        "email_confirmado": True,
                    }).execute()
                    mostrar_popup(f"{nome_membro} cadastrado(a) com sucesso como {cargo_escolhido}!")
                    st.rerun()

    with tab_lista:
        membros_resp = supabase.table("usuarios").select("id, nome, email, perfil, ativo, cargo, permissoes_extras") \
            .eq("empresa_id", emp_id).in_("perfil", ["operador", "gerente"]).order("nome").execute()
        membros = membros_resp.data or []

        if not membros:
            st.info("Nenhum operador ou gerente cadastrado ainda. Use a aba 'Cadastrar Membro'.")
            return

        for m in membros:
            icone_perfil = "🧑‍💼" if m['perfil'] == 'gerente' else "🧾"
            status_txt = "🟢 Ativo" if m['ativo'] else "🔴 Bloqueado"
            cargo_atual = m.get('cargo') or m['perfil'].capitalize()
            with st.expander(f"{icone_perfil} {m['nome']} — {cargo_atual} — {status_txt}"):
                st.write(f"**E-mail:** {m['email']}")

                if m['perfil'] == 'operador':
                    lista_cargos = CARGOS_OPERADOR
                    idx_cargo = lista_cargos.index(cargo_atual) if cargo_atual in lista_cargos else 0
                    novo_cargo = st.selectbox(
                        "Cargo", lista_cargos, index=idx_cargo, key=f"cargo_membro_{m['id']}"
                    )
                    permissoes_atuais = m.get('permissoes_extras') or []
                    st.write("**Páginas liberadas (além do PDV):**")
                    novos_modulos_marcados = []
                    for chave_modulo, label_modulo in MODULOS_EXTRAS_DISPONIVEIS:
                        marcado = st.checkbox(
                            label_modulo,
                            value=chave_modulo in permissoes_atuais,
                            key=f"modulo_membro_{m['id']}_{chave_modulo}"
                        )
                        if marcado:
                            novos_modulos_marcados.append(chave_modulo)
                    if st.button("Salvar cargo/permissões", key=f"salvar_perm_{m['id']}"):
                        supabase.table("usuarios").update({
                            "cargo": novo_cargo,
                            "permissoes_extras": novos_modulos_marcados
                        }).eq("id", m['id']).execute()
                        mostrar_popup("Cargo e permissões atualizados!")
                        st.rerun()

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Bloquear" if m['ativo'] else "Desbloquear", key=f"toggle_membro_{m['id']}"):
                        supabase.table("usuarios").update({"ativo": not m['ativo']}).eq("id", m['id']).execute()
                        st.rerun()
                with col2:
                    nova_senha = st.text_input("Nova senha", key=f"nova_senha_membro_{m['id']}", type="password")
                    if st.button("Redefinir Senha", key=f"btn_redefinir_{m['id']}") and nova_senha:
                        if len(nova_senha) < 7:
                            mostrar_popup("A senha precisa ter no mínimo 7 caracteres.", tipo="erro")
                        else:
                            supabase.table("usuarios").update({"senha_hash": nova_senha}).eq("id", m['id']).execute()
                            mostrar_popup("Senha redefinida!")
