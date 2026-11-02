import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

EMBEDDING_MODEL = os.getenv("GOOGLE_EMBEDDING_MODEL")


def get_embeddings():
    return GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, transport="rest")
