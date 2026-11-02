import os
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from embeddings import get_embeddings

load_dotenv()

PDF_PATH = os.getenv("PDF_PATH")
DATABASE_URL = os.getenv("DATABASE_URL")
COLLECTION_NAME = os.getenv("PG_VECTOR_COLLECTION_NAME")

BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "20"))
PAUSE_SECONDS = int(os.getenv("EMBEDDING_BATCH_PAUSE_SECONDS", "60"))


def ingest_pdf():
    docs = PyPDFLoader(PDF_PATH).load()
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150
    ).split_documents(docs)

    store = PGVector(
        embeddings=get_embeddings(),
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
