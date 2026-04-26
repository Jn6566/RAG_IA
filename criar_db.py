# bibliotecas
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Variáveis Globais
PASTA_BASE = "base"


# Função para criar o banco de dados
def criar_db():
    documentos = carregar_documentos()
    chunks = dividir_chunks(documentos)
    vetorizar_chunks(chunks)


# Carrega os documentos
def carregar_documentos():
    carregador = PyPDFDirectoryLoader(PASTA_BASE, glob="*.pdf")
    documentos = carregador.load()
    return documentos

# Divide o documento em pedaços de 500 caracteres
def dividir_chunks(documentos):
    separador_documentos = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=125, # Isso é uma sobreposição nos chunks usada para evitar textos picotados
        length_function=len,
        add_start_index=True
    )

    chunks = separador_documentos.split_documents(documentos) # Realiza a divisão do PDF
    return chunks

def vetorizar_chunks(chunks):
    db = Chroma.from_documents(chunks, OpenAIEmbeddings(), persist_directory="db")
    print("Banco de dados criado com sucesso!")
    print(f"Chunks Criados: {len(chunks)}")

criar_db()