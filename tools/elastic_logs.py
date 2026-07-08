import os

from elasticsearch import Elasticsearch

ES_URL = os.getenv("ELASTICSEARCH_URL")
INDEX_NAME = "incident-logs"

es = Elasticsearch(ES_URL, request_timeout=30)

def get_es_client():
    try:
        es = Elasticsearch(ES_URL, request_timeout=30)
        if not es.ping():
            return None
        return es
    except Exception:
        return None
    
def create_index():
    print("Checking Elasticsearch connection...")
    es = get_es_client()

    if es is None:
        return "Elasticsearch is not available. Please start Docker/Elasticsearch or ingest logs first."


    if es.indices.exists(index=INDEX_NAME):
        print("Index already exists.")
        return

    es.indices.create(
        index=INDEX_NAME,
        mappings={
            "properties": {
                "source": {"type": "keyword"},
                "line_number": {"type": "integer"},
                "raw_message": {"type": "text"},
                "level": {"type": "keyword"},
                "component": {"type": "keyword"},
                "message": {"type": "text"}
            }
        }
    )

    print("Index created.")


def detect_level(line: str):
    upper = line.upper()

    if "ERROR" in upper or "EXCEPTION" in upper or "FAILED" in upper or "FAILURE" in upper:
        return "ERROR"
    if "WARN" in upper or "WARNING" in upper:
        return "WARN"
    if "INFO" in upper:
        return "INFO"
    if "DEBUG" in upper:
        return "DEBUG"

    return "UNKNOWN"


def ingest_log_file(file_path: str, source: str):
    create_index()

    count = 0

    es = get_es_client()

    if es is None:
        return "Elasticsearch is not available. Please start Docker/Elasticsearch or ingest logs first."


    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            doc = {
                "source": source,
                "line_number": line_number,
                "raw_message": line,
                "level": detect_level(line),
                "component": source,
                "message": line
            }

            es.index(index=INDEX_NAME, document=doc)
            count += 1

    es.indices.refresh(index=INDEX_NAME)
    return count

def search_logs(query: str, size: int = 10):
    # source_filter = detect_source_filter(query)

    bool_query = {
        "must": [
            {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "raw_message^3",
                        "message^2",
                        "source",
                        "level",
                        "component"
                    ],
                    "fuzziness": "AUTO"
                }
            }
        ]
    }

    # if source_filter:
    #     bool_query["filter"] = [
    #         {"term": {"source": source_filter}}
    #     ]

    es = get_es_client()

    if es is None:
        return "Elasticsearch is not available. Please start Docker/Elasticsearch or ingest logs first."

    result = es.search(
        index=INDEX_NAME,
        size=size,
        query={"bool": bool_query}
    )

    hits = result["hits"]["hits"]

    if not hits:
        return f"No matching logs found for query: {query}"

    return "\n".join(
        f"[{hit['_source']['source']} line {hit['_source']['line_number']}] "
        f"{hit['_source']['level']} - {hit['_source']['raw_message']}"
        for hit in hits
    )

def search_error_logs(query: str = "", size: int = 20):
    # source_filter = detect_source_filter(query)

    es = get_es_client()

    if es is None:
        return "Elasticsearch is not available. Please start Docker/Elasticsearch or ingest logs first."

    should_queries = [
        {"match": {"raw_message": "error"}},
        {"match": {"raw_message": "exception"}},
        {"match": {"raw_message": "failed"}},
        {"match": {"raw_message": "failure"}},
        {"match": {"raw_message": "timeout"}},
        {"match": {"raw_message": "killed"}},
        {"match": {"raw_message": "denied"}},
    ]

    if query:
        should_queries.append({
            "multi_match": {
                "query": query,
                "fields": ["raw_message^3", "message^2", "source", "component"]
            }
        })

    bool_query = {
        "should": should_queries,
        "minimum_should_match": 1
    }

    # if source_filter:
    #     bool_query["filter"] = [
    #         {"term": {"source": source_filter}}
    #     ]

    result = es.search(
        index=INDEX_NAME,
        size=size,
        query={"bool": bool_query}
    )

    hits = result["hits"]["hits"]

    if not hits:
        return f"No suspicious logs found for query: {query}"

    return "\n".join(
        f"[{hit['_source']['source']} line {hit['_source']['line_number']}] "
        f"{hit['_source']['level']} - {hit['_source']['raw_message']}"
        for hit in hits
    )

def detect_source_filter(query: str):
    q = query.lower()

    if "linux" in q:
        return "linux"
    if "hadoop" in q:
        return "hadoop"
    if "paymentservice" in q or "userservice" in q or "kafka" in q or "nullpointer" in q:
        return "incident-demo"

    return None

def list_log_sources(query: str = ""):

    es = get_es_client()

    if es is None:
        return "Elasticsearch is not available. Please start Docker/Elasticsearch or ingest logs first."

    result = es.search(
        index=INDEX_NAME,
        size=0,
        aggs={
            "sources": {
                "terms": {
                    "field": "source",
                    "size": 5
                }
            }
        }
    )

    buckets = result["aggregations"]["sources"]["buckets"]

    return "\n".join(
        f"{b['key']}: {b['doc_count']} logs"
        for b in buckets
    )