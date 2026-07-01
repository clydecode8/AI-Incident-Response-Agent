import os
import time
import hashlib
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "incident-knowledge")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768
NAMESPACE = "knowledge"


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def make_vector_id(file_name: str, chunk_index: int, chunk: str):
    raw = f"{file_name}-{chunk_index}-{chunk}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_embedding(client, text: str):
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={
            "output_dimensionality": EMBEDDING_DIMENSION,
        },
    )

    return response.embeddings[0].values


def ensure_index(pc: Pinecone):
    existing_indexes = [index["name"] for index in pc.list_indexes()]

    if PINECONE_INDEX_NAME not in existing_indexes:
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=PINECONE_CLOUD,
                region=PINECONE_REGION,
            ),
        )

        while not pc.describe_index(PINECONE_INDEX_NAME).status["ready"]:
            time.sleep(1)


def main():
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY in .env")

    if not PINECONE_API_KEY:
        raise ValueError("Missing PINECONE_API_KEY in .env")

    if not KNOWLEDGE_DIR.exists():
        raise FileNotFoundError(f"Knowledge folder not found: {KNOWLEDGE_DIR}")

    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    pc = Pinecone(api_key=PINECONE_API_KEY)

    ensure_index(pc)
    index = pc.Index(PINECONE_INDEX_NAME)

    vectors = []

    for file in KNOWLEDGE_DIR.glob("*.md"):
        content = file.read_text(encoding="utf-8")
        chunks = chunk_text(content)

        for chunk_index, chunk in enumerate(chunks):
            embedding = get_embedding(gemini_client, chunk)

            vectors.append({
                "id": make_vector_id(file.name, chunk_index, chunk),
                "values": embedding,
                "metadata": {
                    "source": file.name,
                    "chunk_index": chunk_index,
                    "text": chunk,
                },
            })

    if not vectors:
        print("No markdown knowledge files found.")
        return

    index.upsert(
        vectors=vectors,
        namespace=NAMESPACE,
    )

    print(f"Uploaded {len(vectors)} chunks to Pinecone index '{PINECONE_INDEX_NAME}'.")


if __name__ == "__main__":
    main()