import os

from dotenv import load_dotenv
from google import genai
from pinecone import Pinecone

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "incident-knowledge")

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768
NAMESPACE = "knowledge"

_gemini_client = None
_pinecone_index = None


def get_gemini_client():
    global _gemini_client

    if _gemini_client is None:
        if not GEMINI_API_KEY:
            raise ValueError("Missing GEMINI_API_KEY in .env")

        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    return _gemini_client


def get_pinecone_index():
    global _pinecone_index

    if _pinecone_index is None:
        if not PINECONE_API_KEY:
            raise ValueError("Missing PINECONE_API_KEY in .env")

        pc = Pinecone(api_key=PINECONE_API_KEY)
        _pinecone_index = pc.Index(PINECONE_INDEX_NAME)

    return _pinecone_index


def embed_query(query: str):
    client = get_gemini_client()

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config={
            "output_dimensionality": EMBEDDING_DIMENSION,
        },
    )

    return response.embeddings[0].values


def retrieve_knowledge_docs(query: str, top_k: int = 3) -> str:
    if not query or not query.strip():
        return "No knowledge query provided."

    index = get_pinecone_index()
    query_embedding = embed_query(query)

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        namespace=NAMESPACE,
        include_metadata=True,
    )

    matches = results.get("matches", [])

    if not matches:
        return "No relevant internal knowledge found."

    docs = []

    for match in matches:
        metadata = match.get("metadata", {})
        source = metadata.get("source", "unknown")
        chunk_index = metadata.get("chunk_index", "unknown")
        text = metadata.get("text", "")
        score = match.get("score", 0)

        docs.append(
            f"Source: {source}\n"
            f"Chunk: {chunk_index}\n"
            f"Similarity Score: {score:.4f}\n\n"
            f"{text}"
        )

    return "\n\n---\n\n".join(docs)