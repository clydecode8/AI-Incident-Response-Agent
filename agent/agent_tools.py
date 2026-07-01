from agent.log_reader import LogReader
from agent.log_parser import parse_logs
from agent.log_analyzer import LogAnalyzer
from agent.metrics_tool import read_metrics, summarize_metrics
from agent.knowledge_retriever import retrieve_knowledge_docs

def search_logs(log_path="incident-demo/logs/application.log"):
    """
    Substitute for Elasticsearch/Kibana log search.
    In production, this would query Elasticsearch.
    """
    reader = LogReader(log_path)
    raw_logs = reader.read()
    parsed_logs = parse_logs(raw_logs)
    analyzer = LogAnalyzer(parsed_logs)

    errors = analyzer.get_errors()

    if not errors:
        return "No ERROR logs found."

    latest_error = errors[-1]

    return f"""
        Latest Error Log:
        Service: {latest_error.service}
        Timestamp: {latest_error.timestamp}
        Message: {latest_error.message}
        Exception: {latest_error.exception}
    """


def search_metrics(metrics_path="incident-demo/metrics/metrics.json"):
    """
    Substitute for Grafana/Prometheus metrics.
    In production, this would query Prometheus/Grafana APIs.
    """
    metrics = read_metrics(metrics_path)
    return summarize_metrics(metrics)

def retrieve_knowledge(query: str):
    """
    RAG knowledge retrieval tool.

    Substitute for Confluence internal documentation.
    In production, this would call Confluence API or MCP tool.

    This searches Pinecone using Gemini embeddings.
    It does not replace Elasticsearch.
    Elasticsearch is for logs.
    Pinecone RAG is for internal docs/runbooks.
    """
    return retrieve_knowledge_docs(query)