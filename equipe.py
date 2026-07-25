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
from utils import mostrar_popup, validar_senha_forte, REQUISITOS_SENHA_TEXTO, processar_foto_upload
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
            st.caption(REQUISITOS_SENHA_TEXTO)

            cpf_membro = st.text_input("CPF", placeholder="000.000.000-00")
            telefone_membro = st.text_input("Contato (WhatsApp/telefone)", placeholder="(84) 99999-9999")

            st.markdown("**Endereço**")
            col_end1, col_end2 = st.columns([2.5, 1])
            with col_end1:
                rua_membro = st.text_input("Rua")
            with col_end2:
                numero_membro = st.text_input("Número")
            bairro_membro = st.text_input("Bairro")

            foto_membro = st.file_uploader("Foto (opcional)", type=["png", "jpg", "jpeg"])

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
            senha_ok, msg_senha_erro = validar_senha_forte(senha_membro)
            if not nome_membro.strip() or not email_membro.strip():
                mostrar_popup("Preencha nome e e-mail.", tipo="erro")
            elif not senha_ok:
                mostrar_popup(msg_senha_erro, tipo="erro")
            else:
                email_existente = supabase.table("usuarios").select("id").eq("email", email_membro.strip()).execute()
                if email_existente.data:
                    mostrar_popup("Já existe uma conta com esse e-mail.", tipo="erro")
                else:
                    dados_novo_membro = {
                        "empresa_id": emp_id,
                        "nome": nome_membro.strip(),
                        "email": email_membro.strip(),
                        "senha_hash": senha_membro,
                        "perfil": perfil_escolhido,
                        "cargo": cargo_escolhido,
                        "permissoes_extras": modulos_marcados,
                        "cpf": cpf_membro.strip() or None,
                        "telefone": telefone_membro.strip() or None,
                        "endereco_rua": rua_membro.strip() or None,
                        "endereco_numero": numero_membro.strip() or None,
                        "endereco_bairro": bairro_membro.strip() or None,
                        "ativo": True,
                        "email_confirmado": True,
                    }
                    if foto_membro is not None:
                        foto_processada = processar_foto_upload(foto_membro)
                        if foto_processada:
                            dados_novo_membro["foto_base64"] = foto_processada

                    supabase.table("usuarios").insert(dados_novo_membro).execute()
                    mostrar_popup(f"{nome_membro} cadastrado(a) com sucesso como {cargo_escolhido}!")
                    st.rerun()

    with tab_lista:
        membros_resp = supabase.table("usuarios").select(
            "id, nome, email, perfil, ativo, cargo, permissoes_extras, "
            "foto_base64, cpf, telefone, endereco_rua, endereco_numero, endereco_bairro"
        ).eq("empresa_id", emp_id).in_("perfil", ["operador", "gerente"]).order("nome").execute()
        membros = membros_resp.data or []

        if not membros:
            st.info("Nenhum operador ou gerente cadastrado ainda. Use a aba 'Cadastrar Membro'.")
            return

        for m in membros:
            icone_perfil = "🧑‍💼" if m['perfil'] == 'gerente' else "🧾"
            status_txt = "🟢 Ativo" if m['ativo'] else "🔴 Bloqueado"
            cargo_atual = m.get('cargo') or m['perfil'].capitalize()
            with st.expander(f"{icone_perfil} {m['nome']} — {cargo_atual} — {status_txt}"):
                col_foto_m, col_info_m = st.columns([1, 3])
                with col_foto_m:
                    foto_membro_atual = m.get('foto_base64')
                    if foto_membro_atual:
                        st.markdown(
                            f"""<img src="data:image/jpeg;base64,{foto_membro_atual}"
                                style="width:90px;height:90px;border-radius:50%;object-fit:cover;
                                border:2px solid #3B82F6;" />""",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            """<div style="width:90px;height:90px;border-radius:50%;background-color:#5F6368;
                                display:flex;align-items:center;justify-content:center;border:2px solid #3B82F6;">
                                <svg viewBox="0 0 24 24" width="50" height="50" fill="white">
                                    <circle cx="12" cy="8" r="4"/>
                                    <path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6v1H4v-1z"/>
                                </svg>
                            </div>""",
                            unsafe_allow_html=True
                        )
                with col_info_m:
                    st.write(f"**E-mail:** {m['email']}")
                    st.write(f"**CPF:** {m.get('cpf') or '— não informado —'}")
                    st.write(f"**Contato:** {m.get('telefone') or '— não informado —'}")
                    endereco_partes = [p for p in [m.get('endereco_rua'), m.get('endereco_numero'), m.get('endereco_bairro')] if p]
                    st.write(f"**Endereço:** {', '.join(endereco_partes) if endereco_partes else '— não informado —'}")

                st.markdown("**Editar dados cadastrais**")
                novo_cpf_m = st.text_input("CPF", value=m.get('cpf') or "", key=f"cpf_membro_{m['id']}")
                novo_telefone_m = st.text_input("Contato", value=m.get('telefone') or "", key=f"tel_membro_{m['id']}")
                col_end_m1, col_end_m2 = st.columns([2.5, 1])
                with col_end_m1:
                    nova_rua_m = st.text_input("Rua", value=m.get('endereco_rua') or "", key=f"rua_membro_{m['id']}")
                with col_end_m2:
                    novo_numero_m = st.text_input("Número", value=m.get('endereco_numero') or "", key=f"num_membro_{m['id']}")
                novo_bairro_m = st.text_input("Bairro", value=m.get('endereco_bairro') or "", key=f"bairro_membro_{m['id']}")
                nova_foto_m = st.file_uploader("Trocar foto", type=["png", "jpg", "jpeg"], key=f"foto_membro_{m['id']}")

                if st.button("Salvar dados cadastrais", key=f"salvar_dados_{m['id']}"):
                    dados_atualizar_membro = {
                        "cpf": novo_cpf_m.strip() or None,
                        "telefone": novo_telefone_m.strip() or None,
                        "endereco_rua": nova_rua_m.strip() or None,
                        "endereco_numero": novo_numero_m.strip() or None,
                        "endereco_bairro": novo_bairro_m.strip() or None,
                    }
                    if nova_foto_m is not None:
                        foto_processada_m = processar_foto_upload(nova_foto_m)
                        if foto_processada_m:
                            dados_atualizar_membro["foto_base64"] = foto_processada_m
                    supabase.table("usuarios").update(dados_atualizar_membro).eq("id", m['id']).execute()
                    mostrar_popup("Dados cadastrais atualizados!")
                    st.rerun()

                st.markdown("---")

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
                    st.caption(REQUISITOS_SENHA_TEXTO)
                    if st.button("Redefinir Senha", key=f"btn_redefinir_{m['id']}") and nova_senha:
                        senha_ok_membro, msg_senha_membro = validar_senha_forte(nova_senha)
                        if not senha_ok_membro:
                            mostrar_popup(msg_senha_membro, tipo="erro")
                        else:
                            supabase.table("usuarios").update({"senha_hash": nova_senha}).eq("id", m['id']).execute()
                            mostrar_popup("Senha redefinida!")
