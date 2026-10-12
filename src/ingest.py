import os
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

PDF_PATH = os.getenv("PDF_PATH")
DATABASE_URL = os.getenv("DATABASE_URL")
COLLECTION_NAME = os.getenv("PG_VECTOR_COLLECTION_NAME")
EMBEDDING_MODEL = os.getenv("GOOGLE_EMBEDDING_MODEL")

BATCH_SIZE = 20
PAUSE_SECONDS = 60


def ingest_pdf():
    docs = PyPDFLoader(PDF_PATH).load()
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150
    ).split_documents(docs)

    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    store = PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=DATABASE_URL,
        use_jsonb=True,
    )
    store.delete_collection()
    store.create_collection()
    for i in range(0, len(chunks), BATCH_SIZE):
        store.add_documents(chunks[i:i + BATCH_SIZE])
        print(f"{min(i + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks gravados")
        if i + BATCH_SIZE < len(chunks):
            time.sleep(PAUSE_SECONDS)
    print(f"{len(chunks)} chunks gravados em '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    ingest_pdf()
