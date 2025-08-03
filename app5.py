import streamlit as st
import pandas as pd
import pyttsx3
from datetime import datetime, date
import uuid
from PIL import Image
import base64
import os

import firebase_admin
from firebase_admin import credentials, firestore

import cloudinary
import cloudinary.uploader
from google.cloud.firestore_v1 import DocumentSnapshot
from firebase_admin.firestore import SERVER_TIMESTAMP

# --- Configuração da página ---
st.set_page_config(page_title="Cantinho da Memória", layout="wide")

# --- Estilo visual aprimorado para acessibilidade ---
st.markdown("""
<style>
    /* Aumenta a fonte base para melhor legibilidade em todas as telas */
    html, body, [class*="st-"] { font-size: 20px; }

    /* Estilo padrão para títulos em modo claro */
    h1 { font-size: 3.5em; color: #2a2a2a; }
    h2 { font-size: 2.5em; color: #444444; }
    h3 { font-size: 2em; color: #666666; }

    /* Ajuste de cores para modo escuro */
    @media (prefers-color-scheme: dark) {
        h1 { color: #f0f0f0; }
        h2 { color: #e0e0e0; }
        h3 { color: #cccccc; }
    }

    /* Botões maiores, com bordas arredondadas e efeito suave */
    div.stButton > button {
        font-size: 22px;
        padding: 12px 24px;
        height: auto;
        width: 100%;
        margin-top: 10px;
        border-radius: 8px;
        border: 2px solid #a3b18a; /* Borda suave */
        background-color: #fefefe;
        color: #4a4a4a;
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        background-color: #a3b18a; /* Cor de destaque ao passar o mouse */
        color: white;
        border-color: #a3b18a;
    }

    /* Estilo para os cards de conteúdo */
    .st-emotion-cache-1pxx5e4 {
        border-radius: 10px;
        background-color: #f8f9fa;
        padding: 20px;
        margin-bottom: 15px;
        border: 1px solid #e0e0e0;
    }
    /* Estilo para a caixa de seleção da rotina concluída */
    .stCheckbox > label > div {
        color: #6e6e6e;
    }
    .stCheckbox > label > div.st-emotion-cache-13hv875 {
        color: #a3b18a;
        text-decoration: line-through;
    }

    /* Estilo do menu de navegação */
    .stRadio > label {
        font-size: 22px;
        padding: 10px 0;
        margin-bottom: 5px;
    }
    .stSuccess { background-color: #e6ffe6; border-left: 5px solid #4caf50; }
    .stWarning { background-color: #fff8e1; border-left: 5px solid #ffc107; }
    .stError { background-color: #ffebee; border-left: 5px solid #f44336; }

    /* CORREÇÃO DO PROBLEMA DE QUEBRA DE PALAVRAS */
    p {
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
</style>
""", unsafe_allow_html=True)

# --- Configuração da Voz ---
if "voz_ativada" not in st.session_state:
    st.session_state.voz_ativada = True

def falar(texto):
    """
    Função de fala aprimorada, agora com verificação do estado da voz.
    """
    if st.session_state.voz_ativada:
        try:
            engine = pyttsx3.init()
            engine.say(texto)
            engine.runAndWait()
        except Exception as e:
            print(f"Erro na função de fala: {e}")

# --- Firebase ---
if not firebase_admin._apps:
    try:
        cred_data = dict(st.secrets["firebase_config"])
        cred = credentials.Certificate(cred_data)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"❌ Erro ao iniciar Firebase: {e}")
        st.stop()

db = firestore.client()

# --- Cloudinary ---
cloudinary.config(
    cloud_name = st.secrets["cloudinary"]["cloud_name"],
    api_key = st.secrets["cloudinary"]["api_key"],
    api_secret = st.secrets["cloudinary"]["api_secret"]
)

# --- Autenticação e estado da sessão (melhorado) ---
if "user_id" not in st.session_state or st.session_state["user_id"] is None:
    
    st.title("Bem-vindo(a) ao Cantinho da Memória!")
    st.info("Para começar, digite seu código de acesso ou crie um novo.")
    
    with st.expander("🔑 Já tenho um código de acesso"):
        login_code = st.text_input("Digite seu código de 4 dígitos", key="login_code_input").strip()
        
        # Obter a pergunta secreta do usuário, se o código for válido
        if login_code and login_code.isdigit() and len(login_code) == 4:
            user_ref = db.collection("users").where("access_code", "==", login_code).limit(1).stream()
            user_docs = list(user_ref)
            if user_docs:
                user_data = user_docs[0].to_dict()
                secret_question = user_data.get("secret_question", "Pergunta secreta")
                login_secret_answer = st.text_input(f"Responda: {secret_question}", key="login_answer_input").strip()

                if st.button("Entrar", key="login_button"):
                    if login_secret_answer == user_data.get("secret_answer"):
                        st.session_state["user_id"] = user_docs[0].id
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Resposta secreta inválida.")
            else:
                st.error("❌ Código de acesso inválido.")
        else:
            st.warning("Por favor, digite um código de 4 dígitos para continuar.")
    
    with st.expander("🆕 Criar meu Cantinho da Memória"):
        new_access_code = st.text_input("Escolha um código de 4 dígitos", key="new_code_input").strip()
        st.info("Agora, escolha uma pergunta e resposta secreta para sua segurança.")
        
        secret_question_options = [
            "Qual o seu apelido de infância?",
            "Qual a cidade em que você nasceu?",
            "Qual o nome do seu animal de estimação?",
            "Qual a sua comida favorita?",
            "Qual o nome da sua mãe?"
        ]
        new_secret_question = st.selectbox("Escolha uma pergunta secreta", secret_question_options)
        new_secret_answer = st.text_input("Sua resposta secreta", key="new_answer_input").strip()

        if st.button("Criar e Entrar"):
            if new_access_code and new_access_code.isdigit() and len(new_access_code) == 4 and new_secret_answer:
                # Verificar se o código já existe
                existing_user_ref = db.collection("users").where("access_code", "==", new_access_code).limit(1).stream()
                if list(existing_user_ref):
                    st.error("❌ Este código já está em uso. Por favor, escolha outro.")
                else:
                    # Criar um novo usuário no Firestore
                    new_user_ref = db.collection("users").add({
                        "access_code": new_access_code,
                        "secret_question": new_secret_question,
                        "secret_answer": new_secret_answer,
                        "created_at": firestore.SERVER_TIMESTAMP
                    })
                    st.session_state["user_id"] = new_user_ref[1].id
                    
                    st.success(f"Seu Cantinho da Memória foi criado! Seu código é: {new_access_code}")
                    st.info("Guarde-o junto com sua pergunta secreta. Agora você pode entrar com eles a qualquer momento.")
                    st.rerun()
            else:
                st.warning("Por favor, digite um código de 4 dígitos e a resposta para a pergunta secreta.")
            
    st.stop()
    
# --- Título do App (somente aparece após o login) ---
st.title("🌸 Cantinho da Memória")
st.markdown("_Um espaço seguro para suas lembranças._")

# --- Menu de Navegação ---
st.sidebar.success(f"Você está conectado(a). ID: {st.session_state['user_id'][:8]}...")
st.sidebar.markdown("---")
st.sidebar.toggle("🔊 Ativar/Desativar Voz", key="voz_ativada")

menu = st.sidebar.radio(
    "O que você gostaria de fazer hoje?", 
    ["📅 Lembretes", "📝 Notas", "🧺 Minhas Memórias", "📋 Minha Rotina Diária", "⏰ Meus Remédios"]
)

# AVISO DE PRIVACIDADE ABAIXO DO MENU
with st.sidebar.expander("🛡️ Sobre seus dados e privacidade"):
    st.info("""
        **Aviso Importante:** Suas anotações, lembretes e fotos são armazenadas em serviços de nuvem seguros. Para fins de manutenção e suporte do aplicativo, o administrador do sistema tem acesso a esses dados. Suas informações são tratadas com total respeito e confidencialidade.
    """)

# --- Botão de Sair ---
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sair do Cantinho"):
    st.session_state["user_id"] = None
    st.success("Você saiu com sucesso!")
    st.rerun()

# --- Logo no final da barra lateral (CORRIGIDO) ---
st.sidebar.markdown("---")
try:
    # Lê a imagem em bytes e a converte para base64 para embedar diretamente no HTML
    image_path = "logo_suzika.png"
    if os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        
        # O HTML e CSS garantem que a imagem seja centralizada de forma confiável
        st.sidebar.markdown(
            f"""
            <div style="display: flex; justify-content: center; margin-bottom: 10px;">
                <img src="data:image/png;base64,{encoded_string}" width="120">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.sidebar.error("❌ Logo não encontrado: `logo_suzika.png`")

except Exception as e:
    st.sidebar.error(f"Erro ao carregar a logo: {e}")

st.markdown("---")

# --- Lembretes ---
if menu == "📅 Lembretes":
    st.header("📝 Criar Lembrete")
    st.info("O que é importante para você lembrar? Vamos anotar juntos.")
    
    tarefa = st.text_input("Tarefa")
    data_lembrete_str = st.text_input("Data do Lembrete (formato DD/MM/AAAA)", value=datetime.now().strftime("%d/%m/%Y"))
    hora_str = st.text_input("Horário (formato HH:MM)", value=datetime.now().strftime("%H:%M"))
    repeticao = st.selectbox("Repetição", ["Nenhuma", "Diária", "Semanal", "Mensal"])

    if st.button("➕ Salvar Lembrete"):
        if not tarefa:
            st.warning("Digite a tarefa.")
            falar("Por favor, digite a tarefa para poder salvar.")
        else:
            try:
                datetime.strptime(data_lembrete_str, "%d/%m/%Y")
                datetime.strptime(hora_str, "%H:%M")
                
                db.collection("lembretes").add({
                    "user_id": st.session_state["user_id"],
                    "Tarefa": tarefa,
                    "Data": data_lembrete_str,
                    "Hora": hora_str,
                    "Repetição": repeticao,
                    "CriadoEm": firestore.SERVER_TIMESTAMP
                })
                st.success("Lembrete salvo!")
                falar(f"Lembrete salvo com sucesso. A tarefa é: {tarefa}.")
                st.rerun()
            except ValueError:
                st.error("❌ Por favor, use os formatos corretos de data (DD/MM/AAAA) e hora (HH:MM).")
                falar("Erro. Por favor, use os formatos corretos de data e hora.")
            except Exception as e:
                st.error(f"Erro: {e}")
                falar("Houve um erro ao salvar o lembrete.")

    st.subheader("🔔 Meus Lembretes")
    try:
        lembretes_ref = db.collection("lembretes").where(
            "user_id", "==", st.session_state["user_id"]
        ).stream()
        
        lembretes_com_id = [{"ID": doc.id, **doc.to_dict()} for doc in lembretes_ref]

        if lembretes_com_id:
            def get_sort_key(item):
                data = item.get("Data")
                hora = item.get("Hora", "00:00")
                try:
                    return datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M")
                except (ValueError, TypeError):
                    return datetime.min

            lembretes_ordenados = sorted(lembretes_com_id, key=get_sort_key, reverse=True)

            for item in lembretes_ordenados:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([5, 1, 1])
                    with col1:
                        data_formatada = item.get("Data", "Sem Data")
                        st.markdown(f"**{item.get('Tarefa', 'Sem Tarefa')}** em **{data_formatada}** às {item.get('Hora', 'Sem Hora')} — {item.get('Repetição', 'Nenhuma')}")
                    with col2:
                        if st.button("▶️", key=f"ouvir_lembrete_{item['ID']}"):
                            falar(f"Lembrete: {item.get('Tarefa')}, no dia {data_formatada}, às {item.get('Hora')}.")
                    with col3:
                        if st.button("❌", key=f"lembrete_{item['ID']}"):
                            db.collection("lembretes").document(item['ID']).delete()
                            st.success("Lembrete removido!")
                            falar("Lembrete removido com sucesso.")
                            st.rerun()
            
            df = pd.DataFrame(lembretes_ordenados)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📂",
                data=csv,
                file_name="meus_lembretes.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhum lembrete encontrado. Que tal criar um novo?")

    except Exception as e:
        st.error(f"Erro ao carregar lembretes: {e}")
        falar("Houve um erro ao carregar os lembretes.")

# --- Notas ---
elif menu == "📝 Notas":
    st.header("✏️ Escrever uma Nova Nota")
    st.info("Registre seus pensamentos, sentimentos ou qualquer coisa que queira guardar.")
    
    nota = st.text_area("Escreva sua nota")

    if st.button("➕ Salvar Nota"):
        if not nota:
            st.warning("Digite algo.")
            falar("Por favor, digite a sua nota para poder salvar.")
        else:
            try:
                db.collection("notas").add({
                    "user_id": st.session_state["user_id"],
                    "Nota": nota,
                    "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "CriadoEm": firestore.SERVER_TIMESTAMP
                })
                st.success("Nota registrada!")
                falar("Nota salva com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar nota: {e}")
                falar("Houve um erro ao salvar a nota.")

    st.subheader("📚 Minhas Notas")
    try:
        notas_ref = db.collection("notas").where(
            "user_id", "==", st.session_state["user_id"]
        ).stream()

        notas_com_id = [{"ID": doc.id, **doc.to_dict()} for doc in notas_ref]

        if notas_com_id:
            for item in notas_com_id:
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"**{item.get('Nota', 'Sem Nota')}** (_{item.get('Data', 'Sem Data')}_)")
                with col2:
                    if st.button("❌", key=f"nota_{item['ID']}"):
                        db.collection("notas").document(item['ID']).delete()
                        st.rerun()
                        falar("Nota removida.")
            
            df = pd.DataFrame(notas_com_id)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📂",
                data=csv,
                file_name="minhas_notas.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhuma nota encontrada. Que tal registrar a primeira?")
    except Exception as e:
        st.error(f"Erro ao carregar notas: {e}")
        falar("Houve um erro ao carregar as notas.")

# --- Memórias ---
elif menu == "🧺 Minhas Memórias":
    st.header("🖼️ Minhas Memórias")
    st.info("Aqui estão os momentos que você guardou com carinho. Que tal criar um novo?")
    
    FOTOS_LIMITE = 5
    
    memorias_ref_count = db.collection("memorias").where(
        "user_id", "==", st.session_state["user_id"]
    ).stream()
    num_fotos_existentes = sum(1 for _ in memorias_ref_count)

    with st.expander("➕ Registrar uma lembrança especial"):
        st.info(f"Você tem {num_fotos_existentes}/{FOTOS_LIMITE} fotos registradas.")
        
        if num_fotos_existentes >= FOTOS_LIMITE:
            st.warning("Você atingiu o limite de fotos. Exclua uma foto para adicionar uma nova.")
        else:
            titulo = st.text_input("Título da memória")
            descricao = st.text_area("Descrição")
            uploaded_file = st.file_uploader("Foto da memória (opcional)", type=["jpg", "jpeg", "png"])

            if st.button("➕ Salvar Memória"):
                if not titulo or not descricao:
                    st.warning("Preencha título e descrição.")
                    falar("Por favor, preencha o título e a descrição da memória para poder salvar.")
                else:
                    try:
                        image_url = None
                        if uploaded_file:
                            result = cloudinary.uploader.upload(uploaded_file, folder="memorias")
                            image_url = result["secure_url"]

                        db.collection("memorias").add({
                            "user_id": st.session_state["user_id"],
                            "Título": titulo,
                            "Descrição": descricao,
                            "ImagemURL": image_url,
                            "CriadoEm": firestore.SERVER_TIMESTAMP
                        })
                        st.success("🌸 Memória registrada com carinho!")
                        falar(f"Memória registrada com sucesso: {titulo}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar memória: {e}")
                        falar("Houve um erro ao salvar a memória.")

    st.subheader("📖 Memórias guardadas com afeto")
    try:
        memorias_ref = db.collection("memorias").where(
            "user_id", "==", st.session_state["user_id"]
        ).order_by("CriadoEm", direction=firestore.Query.DESCENDING).stream()

        minhas_memorias = []
        for doc in memorias_ref:
            item = doc.to_dict()
            item["ID"] = doc.id
            minhas_memorias.append(item)

            with st.container(border=True):
                st.markdown(f"**{item.get('Título', 'Sem título')}**")
                st.markdown(f"_{item.get('Descrição', 'Sem descrição')}_")
                if item.get("ImagemURL"):
                    st.image(item["ImagemURL"], caption="🖼️ Foto da memória", use_column_width=True)
                
                col1, col2 = st.columns([1,1])
                with col1:
                    if st.button("❌", key=f"memoria_del_{item['ID']}"):
                        try:
                            db.collection("memorias").document(item["ID"]).delete()
                            st.success("Memória removida!")
                            falar("Memória removida com sucesso.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao deletar memória: {e}")
                            falar("Houve um erro ao deletar a memória.")
                with col2:
                    if st.button("▶️", key=f"ouvir_memoria_{doc.id}"):
                        falar(f"Título: {item.get('Título')}. Descrição: {item.get('Descrição')}")

        if minhas_memorias:
            df = pd.DataFrame(minhas_memorias)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📂",
                data=csv,
                file_name="minhas_memorias.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhuma memória encontrada. Que tal registrar a primeira?")
    except Exception as e:
        st.error(f"Erro ao carregar memórias: {e}")
        falar("Houve um erro ao carregar as memórias.")

# --- Minha Rotina Diária ---
elif menu == "📋 Minha Rotina Diária":
    st.header("📋 Minha Rotina Diária")
    st.info("Adicione tarefas fixas para o seu dia. Marque-as como concluídas para acompanhar seu progresso.")
    
    nova_tarefa = st.text_input("Qual tarefa você quer adicionar?")
    if st.button("➕ Adicionar Tarefa"):
        if nova_tarefa:
            try:
                db.collection("rotinas").add({
                    "user_id": st.session_state["user_id"],
                    "Tarefa": nova_tarefa,
                    "Concluida": False,
                    "CriadoEm": firestore.SERVER_TIMESTAMP
                })
                st.success(f"Tarefa '{nova_tarefa}' adicionada à sua rotina!")
                falar(f"Tarefa adicionada: {nova_tarefa}.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar a tarefa: {e}")
                falar("Houve um erro ao salvar a tarefa.")
        else:
            st.warning("O campo da tarefa não pode estar vazio.")
            falar("Por favor, adicione uma tarefa para poder salvar.")

    st.subheader("✅ Minhas Tarefas de Hoje")
    try:
        rotinas_ref = db.collection("rotinas").where(
            "user_id", "==", st.session_state["user_id"]
        ).order_by("CriadoEm").stream()

        rotinas_com_id = [{"ID": doc.id, **doc.to_dict()} for doc in rotinas_ref]

        if rotinas_com_id:
            for item in rotinas_com_id:
                with st.container(border=True):
                    col1, col2 = st.columns([10, 1])

                    concluida_status = col1.checkbox(
                        item.get("Tarefa", "Tarefa sem nome"), 
                        value=item.get("Concluida", False), 
                        key=f"rotina_{item['ID']}"
                    )

                    if concluida_status != item.get("Concluida", False):
                        db.collection("rotinas").document(item['ID']).update({"Concluida": concluida_status})
                        falar(f"Tarefa {item.get('Tarefa')} marcada como {'concluída' if concluida_status else 'pendente'}.")
                        st.rerun()

                    with col2:
                        if st.button("❌", key=f"remover_rotina_{item['ID']}"):
                            db.collection("rotinas").document(item['ID']).delete()
                            st.success("Tarefa removida!")
                            falar("Tarefa removida com sucesso.")
                            st.rerun()
            
            df = pd.DataFrame(rotinas_com_id)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📂",
                data=csv,
                file_name="minha_rotina.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhuma tarefa de rotina encontrada. Adicione a primeira!")
    except Exception as e:
        st.error(f"Erro ao carregar a rotina: {e}")
        falar("Houve um erro ao carregar a rotina.")

# --- Meus Remédios ---
elif menu == "⏰ Meus Remédios":
    st.header("💊 Registrar um Remédio")
    st.info("Adicione aqui os remédios e os horários para não esquecer de tomar.")
    
    remedio_nome = st.text_input("Nome do Remédio")
    remedio_horario = st.text_input("Horário (ex: 10:00, 18:30)")
    remedio_frequencia = st.text_input("Frequência (ex: 8 em 8 horas, 1 vez ao dia)")

    if st.button("➕ Salvar Remédio"):
        if not remedio_nome or not remedio_horario:
            st.warning("Preencha pelo menos o nome e o horário do remédio.")
            falar("Por favor, preencha o nome e o horário do remédio para poder salvar.")
        else:
            try:
                db.collection("remedios").add({
                    "user_id": st.session_state["user_id"],
                    "Nome": remedio_nome,
                    "Horario": remedio_horario,
                    "Frequencia": remedio_frequencia,
                    "CriadoEm": firestore.SERVER_TIMESTAMP
                })
                st.success(f"Remédio '{remedio_nome}' salvo com sucesso!")
                falar(f"Remédio {remedio_nome} foi salvo com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar o remédio: {e}")
                falar("Houve um erro ao salvar o remédio.")

    st.subheader("📋 Meus Remédios Registrados")
    try:
        remedios_ref = db.collection("remedios").where(
            "user_id", "==", st.session_state["user_id"]
        ).stream()

        remedios_com_id = [{"ID": doc.id, **doc.to_dict()} for doc in remedios_ref]

        if remedios_com_id:
            for item in remedios_com_id:
                with st.container(border=True):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"**{item.get('Nome', 'Sem nome')}** - Horário: {item.get('Horario', 'Não especificado')}")
                        if item.get("Frequencia"):
                            st.markdown(f"Frequência: _{item.get('Frequencia')}_")
                    with col2:
                        if st.button("❌", key=f"remedio_{item['ID']}"):
                            db.collection("remedios").document(item['ID']).delete()
                            st.success("Remédio removido!")
                            falar("Remédio removido com sucesso.")
                            st.rerun()
            
            df = pd.DataFrame(remedios_com_id)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📂",
                data=csv,
                file_name="meus_remedios.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhum remédio registrado. Adicione o primeiro!")
    except Exception as e:
        st.error(f"Erro ao carregar a lista de remédios: {e}")
        falar("Houve um erro ao carregar a lista de remédios.")