import os
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
COLLECTION_NAME = os.getenv("PG_VECTOR_COLLECTION_NAME")
EMBEDDING_MODEL = os.getenv("GOOGLE_EMBEDDING_MODEL")
LLM_MODEL = os.getenv("GOOGLE_LLM_MODEL")

REQUIRED_ENV = [
    "GOOGLE_API_KEY",
    "DATABASE_URL",
    "PG_VECTOR_COLLECTION_NAME",
    "GOOGLE_EMBEDDING_MODEL",
    "GOOGLE_LLM_MODEL",
]

TOP_K = 10

PROMPT_TEMPLATE = """
CONTEXTO:
{contexto}

REGRAS:
- Responda somente com base no CONTEXTO.
- Se a informação não estiver explicitamente no CONTEXTO, responda:
  "Não tenho informações necessárias para responder sua pergunta."
- Nunca invente ou use conhecimento externo.
- Nunca produza opiniões ou interpretações além do que está escrito.

EXEMPLOS DE PERGUNTAS FORA DO CONTEXTO:
Pergunta: "Qual é a capital da França?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Quantos clientes temos em 2024?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Você acha isso bom ou ruim?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

PERGUNTA DO USUÁRIO:
{pergunta}

RESPONDA A "PERGUNTA DO USUÁRIO"
"""


def get_store():
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=DATABASE_URL,
        use_jsonb=True,
    )


def search_context(question, store=None):
    store = store or get_store()
    return store.similarity_search_with_score(question, k=TOP_K)


def build_context(results):
    return "\n\n---\n\n".join(doc.page_content for doc, _ in results)


def search_prompt(question=None):
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        print(f"Variáveis ausentes no .env: {', '.join(missing)}")
        return None

    try:
        store = get_store()
        llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)
    except Exception as e:
        print(f"Erro ao inicializar a busca: {e}")
        return None

    prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)
    retrieve = RunnableLambda(lambda q: build_context(search_context(q, store)))
    chain = (
        {"contexto": retrieve, "pergunta": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain.invoke(question) if question else chain


if __name__ == "__main__":
    questions = [
        ("Qual o faturamento da empresa SuperTechIABrazil?", "SuperTechIABrazil"),
        ("Em que ano foi fundada a Alfa Energia S.A.?", "Alfa Energia S.A."),
        ("Qual o faturamento da Aurora Educação EPP?", "Aurora Educação EPP"),
        ("Qual é a capital da França?", None),
    ]
    store = get_store()
    for question, expected in questions:
        print(f"\n=== {question}")
        for doc, score in search_context(question, store):
            hit = "✓" if expected and expected in doc.page_content else " "
            snippet = doc.page_content[:80].replace("\n", " ")
            print(f"{hit} {score:.4f} | p.{doc.metadata.get('page')} | {snippet}")
