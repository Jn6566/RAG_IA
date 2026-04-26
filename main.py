# bibliotecas
import threading
from dotenv import load_dotenv
from langchain_chroma.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from templates import prompt_template

# Carrega a chave da API da OpenAI
load_dotenv()

# Configura o modelo usado pela IA
modelo_IA = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.3
)

# Cria controle de usuários
usuarios_sessao = {}
usuarios_lock = threading.Lock()

# Caminho para o Banco de Dados
CAMINHO_DB = "db"
db = None
db_lock = threading.Lock()

# Tempo de inatividade para mandar a mensagem consolidada
TEMPO_ESPERA = 15  # segundos

# Timer de avaliação após encerramento do atendimento
TEMPO_AVALIACAO = 20 * 60  # 20 minutos em segundos


########################## Função utilitária da sessão ##########################
def inicializar_sessao_usuario(user_id):
    """
    Garante que a estrutura da sessão do usuário exista.
    """
    with usuarios_lock:
        if user_id not in usuarios_sessao:
            usuarios_sessao[user_id] = {
                "historico": [],
                "atendimento_humano": False,
                "timer_avaliacao": None,
                "aguardando_avaliacao": False,
                "buffer_perguntas": [],
                "timer_buffer": None,
                "lock": threading.Lock()
            }


########################## Função Carregar DB ##########################
def carregar_db():
    global db
    funcao_embedding = OpenAIEmbeddings()
    db = Chroma(
        persist_directory=CAMINHO_DB,
        embedding_function=funcao_embedding
    )
    return db


########################## Função Cancelar Avaliação ##########################
def cancelar_avaliacao(user_id, motivo=""):
    """
    Cancela o timer de avaliação, se existir, e remove o estado
    de aguardando avaliação.
    """
    inicializar_sessao_usuario(user_id)
    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        timer_avaliacao = sessao.get("timer_avaliacao")
        if timer_avaliacao:
            timer_avaliacao.cancel()

        sessao["timer_avaliacao"] = None
        sessao["aguardando_avaliacao"] = False

    if motivo:
        print(f"\n[{user_id}] {motivo}\n")


########################## Função Pedir Avaliação ##########################
def pedir_avaliacao(user_id):
    """
    Envia a avaliação apenas se o usuário ainda estiver sem novas
    interações após o encerramento do atendimento.
    """
    inicializar_sessao_usuario(user_id)
    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        if not sessao["aguardando_avaliacao"]:
            return

        print(f"\n[{user_id}] Seu atendimento foi finalizado 😊")
        print(f"[{user_id}] Quando puder, gostaria de avaliar como foi sua experiência?")
        print(f"[{user_id}] Responda com uma nota de 1 a 5.\n")

        sessao["timer_avaliacao"] = None
        sessao["aguardando_avaliacao"] = False


########################## Função Agendar Avaliação ##########################
def agendar_avaliacao(user_id):
    """
    Agenda o pedido de avaliação para 20 minutos após o encerramento
    do atendimento, desde que o cliente não volte a interagir.
    """
    inicializar_sessao_usuario(user_id)
    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        timer_avaliacao_atual = sessao.get("timer_avaliacao")
        if timer_avaliacao_atual:
            timer_avaliacao_atual.cancel()

        sessao["aguardando_avaliacao"] = True

        novo_timer = threading.Timer(
            TEMPO_AVALIACAO,
            pedir_avaliacao,
            args=[user_id]
        )
        sessao["timer_avaliacao"] = novo_timer
        novo_timer.start()


########################## Função Ativar Atendimento Humano ##########################
def ativar_atendimento_humano(user_id):
    """
    Ativa a janela de atendimento humano e desativa a IA para o usuário.
    """
    inicializar_sessao_usuario(user_id)
    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        sessao["atendimento_humano"] = True

    cancelar_avaliacao(
        user_id,
        "Atendimento humano ativado. A IA foi desativada para este usuário."
    )


########################## Função Encerrar Atendimento Humano ##########################
def encerrar_atendimento_humano(user_id):
    """
    Encerra o atendimento humano, reativa a IA e agenda o envio
    natural da avaliação.
    """
    inicializar_sessao_usuario(user_id)
    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        sessao["atendimento_humano"] = False

    print(f"\n[{user_id}] Atendimento humano encerrado.")
    print(f"[{user_id}] A IA foi reativada para este usuário.\n")

    agendar_avaliacao(user_id)


########################## Função Processar Buffer ##########################
def processar_buffer(user_id):
    """
    Consolida as mensagens do buffer do usuário e envia para o RAG.
    """
    inicializar_sessao_usuario(user_id)
    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        if not sessao["buffer_perguntas"]:
            sessao["timer_buffer"] = None
            return

        pergunta_final = " ".join(sessao["buffer_perguntas"])
        sessao["buffer_perguntas"] = []
        sessao["timer_buffer"] = None

    executar_rag(user_id, pergunta_final)


########################## Função Reiniciar Timer do Buffer ##########################
def reiniciar_timer_buffer(user_id):
    """
    Reinicia o timer de consolidação de mensagens do usuário.
    """
    inicializar_sessao_usuario(user_id)
    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        if sessao["timer_buffer"]:
            sessao["timer_buffer"].cancel()

        sessao["timer_buffer"] = threading.Timer(
            TEMPO_ESPERA,
            processar_buffer,
            args=[user_id]
        )
        sessao["timer_buffer"].start()


########################## Função Executar RAG ##########################
def executar_rag(user_id, pergunta):
    global db

    inicializar_sessao_usuario(user_id)
    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        # Se o cliente voltou a interagir após o encerramento,
        # cancela o envio automático da avaliação.
        if sessao["aguardando_avaliacao"]:
            # solta lock antes de chamar função que também usa lock
            pass

    if usuarios_sessao[user_id]["aguardando_avaliacao"]:
        cancelar_avaliacao(
            user_id,
            "Nova mensagem recebida antes da avaliação. Envio automático da pesquisa reiniciado."
        )

    agendar_avaliacao(user_id)

    with sessao["lock"]:
        # Se estiver em atendimento humano, bloqueia IA
        if sessao["atendimento_humano"]:
            print(f"\n[{user_id}] Atendimento por IA desativado.")
            print(f"[{user_id}] Sua mensagem foi direcionada para o atendimento humano.\n")
            return

    # Confere se o banco de dados foi carregado
    if db is None:
        print(f"[{user_id}] Erro: DB não carregado.")
        return

    # Filtra o banco de dados conforme a pergunta
    with db_lock:
        resultados = db.similarity_search_with_relevance_scores(pergunta, k=3)

    # Informa caso não possua resultado relevante no bd
    if len(resultados) == 0 or resultados[0][1] < 0.70:
        base_conhecimento = ""
        score_log = []
    else:
        base_conhecimento = "\n\n----\n\n".join(
            [r[0].page_content for r in resultados]
        )
        score_log = [r[1] for r in resultados]

    with sessao["lock"]:
        if len(sessao["historico"]) == 0:
            estado_conversa = "INICIO"
        else:
            estado_conversa = "CONTINUACAO"

        sessao["historico"].append(pergunta)

        if len(sessao["historico"]) > 3:
            sessao["historico"].pop(0)

    # Monta o prompt
    prompt = ChatPromptTemplate.from_template(prompt_template)

    # Adiciona o valor das variáveis no prompt
    prompt = prompt.invoke({
        "estado_conversa": estado_conversa,
        "pergunta": pergunta,
        "base_conhecimento": base_conhecimento
    })

    resposta = modelo_IA.invoke(prompt)

    print(f"\n[{user_id}] Resposta da IA:\n{resposta.content}")

    print("\n######## LOG ########\n")
    print(f"- Usuário: {user_id}")
    print(f"- Sessão do usuário: {usuarios_sessao[user_id]}\n")
    print(f"- Pergunta: {pergunta}\n")
    print(f"- Scores: {score_log}\n")
    print("#####################\n")
    print(f"[{user_id}] Realize sua outra pergunta:\n")


########################## Função Receber Mensagem ##########################
def receber_mensagem(user_id, entrada):
    """
    Função central para receber mensagens/comandos de qualquer usuário.
    Essa é a função mais útil para integrar depois com WhatsApp/API.
    """
    inicializar_sessao_usuario(user_id)
    entrada = entrada.strip()

    if entrada.lower() == "/humano":
        ativar_atendimento_humano(user_id)
        return

    if entrada.lower() == "/encerrar":
        encerrar_atendimento_humano(user_id)
        return

    sessao = usuarios_sessao[user_id]

    with sessao["lock"]:
        sessao["buffer_perguntas"].append(entrada)

    reiniciar_timer_buffer(user_id)


########################## Função Perguntar (simulação local) ##########################
def perguntar():
    """
    Simulação local para múltiplos usuários.
    Formato de entrada:
    usuario_1: Olá
    usuario_2: /humano
    """
    print("Comandos disponíveis:")
    print("/humano   -> ativa atendimento humano")
    print("/encerrar -> encerra atendimento humano e agenda avaliação natural")
    print("/sair     -> encerra programa\n")
    print("Formato de teste:")
    print("usuario_1: Olá")
    print("usuario_2: /humano\n")

    while True:
        entrada = input("Digite no formato usuario_id: mensagem\n").strip()

        if entrada.lower() == "/sair":
            exit("Encerrando sistema...")

        if ":" not in entrada:
            print("Entrada inválida. Use o formato: usuario_id: mensagem\n")
            continue

        user_id, mensagem = entrada.split(":", 1)
        user_id = user_id.strip()
        mensagem = mensagem.strip()

        if not user_id or not mensagem:
            print("Entrada inválida. Use o formato: usuario_id: mensagem\n")
            continue

        receber_mensagem(user_id, mensagem)


########################## Main ##########################
def main():
    carregar_db()
    if db is None:
        raise Exception("DB não foi carregado corretamente.")

    perguntar()

    # Ao sair, processa buffers pendentes de todos os usuários
    with usuarios_lock:
        user_ids = list(usuarios_sessao.keys())

    for user_id in user_ids:
        processar_buffer(user_id)


if __name__ == "__main__":
    main()