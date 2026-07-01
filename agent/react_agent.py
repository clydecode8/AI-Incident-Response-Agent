import os
import json
from groq import Groq
from dotenv import load_dotenv
from google import genai
from agent.agent_tools import search_metrics, retrieve_knowledge
from tools.elastic_logs import search_logs, search_error_logs, list_log_sources
from evaluation.agent_evaluator import evaluate_agent_run
from agent.code_search import search_codebase

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

CORRELATION_TERMS = [
    "connection refused",
    "timeout",
    "timed out",
    "no route to host",
    "broker unavailable",
    "downstream",
    "dependency",
    "failed to connect",
    "unreachable",
    "refused",
    "network",
    "socket",
    "rpc",
    "namenode",
    "datanode",
    "kafka",
    "hdfs",
]

MAX_OBSERVATION_CHARS = 1200
MAX_ALERT_CHARS = 1800

def compact_text(text: str, max_chars: int = MAX_OBSERVATION_CHARS) -> str:
    if not text:
        return ""

    # remove duplicate lines while preserving order
    seen = set()
    unique_lines = []

    for line in text.splitlines():
        clean = line.strip()

        if not clean:
            continue

        if clean not in seen:
            seen.add(clean)
            unique_lines.append(clean)

    compacted = "\n".join(unique_lines)

    if len(compacted) > max_chars:
        compacted = compacted[:max_chars] + "\n...[truncated]"

    return compacted

def should_expand_search(observation: str) -> bool:
    """
    Decide whether the investigation should expand beyond the primary log source.
    This stays in the agent layer because it is an investigation decision,
    not a raw search-tool responsibility.
    """

    if not observation:
        return False

    text = observation.lower()

    if "no matching" in text or "not found" in text:
        return False

    return any(term in text for term in CORRELATION_TERMS)


def infer_related_sources(observation: str, current_source: str = "") -> list[str]:
    """
    Suggest related log sources based on evidence.
    This prevents blindly searching every source.
    """

    text = observation.lower()
    current_source = (current_source or "").lower()

    sources = []

    if any(term in text for term in ["kafka", "broker", "payment"]):
        sources.append("application")

    if any(term in text for term in ["hadoop", "hdfs", "namenode", "datanode", "yarn"]):
        sources.append("hadoop")

    if any(term in text for term in ["linux", "permission", "authentication", "kernel", "disk", "memory", "no route to host", "network"]):
        sources.append("linux")

    return [s for s in sources if s != current_source]

TOOLS = {
    "list_log_sources": list_log_sources,
    "search_logs": search_logs,
    "search_error_logs": search_error_logs,
    "search_metrics": search_metrics,
    "retrieve_knowledge": retrieve_knowledge,
    "search_codebase": search_codebase,
}

SYSTEM_PROMPT = """
    You are an AI Site Reliability Engineer agent.

    Available tools:
    1. list_log_sources
    2. search_logs
    3. search_error_logs
    4. search_metrics
    5. retrieve_knowledge
    6. search_codebase

    Rules:
    - Preserve important context from the incident when generating tool inputs.
    - Include relevant service names, systems, components, exception names, error messages, symptoms, technologies, or infrastructure mentioned in the alert whenever available.
    - Avoid vague search inputs that lose important context.
    - Good: {"action":"search_error_logs","input":"authentication failures permission denied login service"}
    - Good: {"action":"search_logs","input":"payment service timeout broker unavailable"}
    - Bad: {"action":"search_error_logs","input":"broad discovery"}
    - Do not invent facts.
    - Start with the most relevant log source based on the alert.
    - Only expand to other log sources if the first evidence indicates cross-service dependency, network issue, timeout, or downstream failure.
    - Do not merge unrelated errors unless timestamps, service names, or dependency evidence show correlation.
    - Do not merge multiple log sources into one root cause unless there is correlation evidence.
    - If logs from multiple sources appear, do not assume they share one root cause.
    - Treat them as separate evidence groups unless there is correlation evidence such as same time window, host, IP, service, dependency, trace ID, deployment, or metric spike.
    - In the final report, separate "Primary suspected incident" from "Other observed anomalies" when correlation is unclear.
    - Use observations from tools as evidence.
    - If multiple unrelated issues are observed, clearly indicate that they may represent separate incidents instead of assuming a single root cause.
    - Respond ONLY in valid compact JSON.
    - When logs identify a specific exception, class, method, service, or component, use search_codebase to locate the relevant implementation and gather supporting evidence before producing the final report.
    - Use search_codebase to identify the likely code location related to the error.
    - Use \\n for line breaks inside the final report.
    - After collecting runtime evidence from logs and/or metrics, retrieve relevant internal knowledge before producing the final report when additional context could help explain the incident or recommend remediation.
    - Use retrieve_knowledge whenever the investigation identifies a service, component, technology, exception, error pattern, or operational issue that may have related documentation, runbooks, deployment guides, or troubleshooting procedures.
    - Construct the retrieve_knowledge query using the most relevant evidence collected so far, including service names, exception names, error messages, technologies, symptoms, and affected components.
    - Do not use generic queries such as "error" or "incident". Preserve as much useful context as possible.
    - Use retrieved knowledge to support root cause analysis and remediation recommendations, but do not treat it as evidence that the incident occurred. Runtime evidence from logs and metrics takes precedence over documentation.
    - The agent decides tools freely, but final answer is only allowed when investigation requirements are satisfied.

    Tool format:
    {"action":"search_error_logs","input":"relevant search query"}

    Final format:
    {"action":"final","answer":"# Incident Report\\n\\n## Summary\\n..."}
"""

def is_extremely_vague_alert(alert: str) -> bool:
    text = (alert or "").strip().lower()
    words = text.split()

    if len(words) <= 2:
        return True

    has_incident_signal = any(x in text for x in [
        "error", "exception", "timeout", "failed", "failing",
        "down", "slow", "unavailable", "refused", "denied",
        "latency", "crash", "disk", "cpu", "memory"
    ])

    has_structure = any(x in text for x in [
        "service:", "symptom:", "possible error:",
        "log source:", "environment:", "severity:"
    ])

    return not has_incident_signal and not has_structure


def call_llm(messages, provider):

    if provider == "gemini":
        prompt = "\n\n".join(
            f"{m['role'].upper()}:\n{m['content']}"
            for m in messages
        )

        response = gemini_client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
        )

        return response.text or ""

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=1200,
    )

    if isinstance(response, dict):
        choice = response["choices"][0]
        message = choice["message"]
        return message.get("content", "")

    choice = response.choices[0]

    if isinstance(choice, dict):
        return choice.get("message", {}).get("content", "")

    message = choice.message

    if isinstance(message, dict):
        return message.get("content", "")

    return message.content


def safe_json_parse(text: str):
    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}") + 1

    if start == -1 or end == 0:
        return {
            "action": "final",
            "answer": text
        }

    json_text = text[start:end]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {
            "action": "final",
            "answer": text
        }

def infer_source_from_tool_input(tool_input: str) -> str:
    text = (tool_input or "").lower()

    if "hadoop" in text or "hdfs" in text or "namenode" in text or "datanode" in text:
        return "hadoop"

    if "linux" in text or "authentication" in text or "permission" in text or "kernel" in text:
        return "linux"

    if "payment" in text or "kafka" in text or "user" in text or "nullpointerexception" in text:
        return "application"

    return ""

def run_react_agent(alert: str, model, max_steps=6):
    alert = compact_text(alert, MAX_ALERT_CHARS)

    if is_extremely_vague_alert(alert):
        final_report = f"""
            ## Investigation Summary

            The submitted alert is too vague to perform reliable root-cause analysis.

            ## Submitted Alert
            {alert}
        """
        result = {
        "trace": [],
        "report": final_report,
        }

        result["evaluation"] = evaluate_agent_run(alert, result)

        return result

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""
                Investigate this incident alert:

                {alert}

                Start by deciding which tool to call.
            """
        }
    ]

    trace = []
    used_logs = False
    used_metrics = False
    used_runbook = False
    used_codebase = False

    def build_result(final_report):
        if isinstance(final_report, str):
            try:
                parsed = json.loads(final_report)

                if isinstance(parsed, dict):
                    final_report = (
                        parsed.get("answer")
                        or parsed.get("report")
                        or final_report
                    )

            except Exception:
                pass

        result = {
            "trace": trace,
            "report": final_report or "No report generated."
        }

        result["evaluation"] = evaluate_agent_run(alert, result)

        return result

    for step in range(max_steps):
        llm_output = call_llm(messages, model)
        decision = safe_json_parse(llm_output)

        action = decision.get("action")
        tool_input = decision.get("input", "")

        if action == "final":
            return build_result(decision.get("answer", "No report generated."))

        if action in ["search_logs", "search_error_logs", "list_log_sources"]:
            used_logs = True
        elif action == "search_metrics":
            used_metrics = True
        elif action == "retrieve_knowledge":
            used_runbook = True
        elif action == "search_codebase":
            used_codebase = True

        if action not in TOOLS:
            return build_result(f"""
                ## Investigation Summary

                The agent requested an unknown tool: `{action}`.

                ## Status

                Investigation incomplete.

                ## Recommended Next Actions

                - Check the agent system prompt.
                - Ensure the tool name is one of the registered tools.
                - Retry the investigation.
            """)

        raw_observation = TOOLS[action](tool_input)
        observation = compact_text(str(raw_observation))

        trace.append({
            "step": len(trace) + 1,
            "action": action,
            "input": tool_input,
            "observation": observation
        })

        if action in ["search_logs", "search_error_logs"]:
            current_source = infer_source_from_tool_input(tool_input)

            if should_expand_search(observation):
                related_sources = infer_related_sources(
                    observation,
                    current_source=current_source
                )

                for related_source in related_sources:
                    expanded_query = (
                        f"{related_source} related dependency errors "
                        f"timeout connection refused"
                    )

                    expanded_raw = TOOLS[action](expanded_query)
                    expanded_observation = compact_text(str(expanded_raw))

                    trace.append({
                        "step": len(trace) + 1,
                        "action": action,
                        "input": expanded_query,
                        "observation": expanded_observation
                    })

                    messages.append({
                        "role": "user",
                        "content": (
                            f"Expanded search in {related_source} logs:\n"
                            f"{expanded_observation}\n\n"
                            "Use this as additional tool evidence. "
                            "Decide the next tool call or produce the final report."
                        )
                    })
            
            if not used_codebase:
                code_raw = TOOLS["search_codebase"](tool_input)
                code_observation = compact_text(str(code_raw))

                used_codebase = True

                trace.append({
                    "step": len(trace) + 1,
                    "action": "search_codebase",
                    "input": tool_input,
                    "observation": code_observation
                })

                messages.append({
                    "role": "user",
                    "content": f"""
                        Codebase search result:

                        {code_observation}

                        Use both the log evidence and code evidence.

                        Before writing the final report, consider whether retrieve_knowledge could provide useful runbook, known-issue, remediation, or operational guidance.

                        If the code and logs are already enough, you may produce the final report.
                        If remediation or known-issue guidance is needed, call retrieve_knowledge.
                    """
                })
                continue

        if action == "retrieve_knowledge":
            messages.append({
                "role": "user",
                "content": """
                    You have now collected logs, metrics, and knowledge evidence.
                    Produce the final incident report now.
                    Return ONLY JSON:
                    {"action":"final","answer":"# Incident Report\\n\\n## Summary\\n..."}
                """
            })

            final_output = call_llm(messages, model)
            final_decision = safe_json_parse(final_output)

            return build_result(final_decision.get("answer", final_output))


        messages.append({
            "role": "assistant",
            "content": json.dumps(decision)
        })

        messages.append({
            "role": "user",
            "content": f"""
                Tool observation from {action}:

                {observation}

                Decide the next tool call or produce the final report.
            """
        })

    return build_result("""
        ## Investigation Summary

        The investigation could not reach a confirmed root cause within the allowed reasoning steps.

        ## Assessment

        The collected evidence was not sufficient to confidently determine the root cause.

        ## Status

        Investigation incomplete due to insufficient evidence.

        ## Recommended Next Actions

        - Provide a more specific alert message.
        - Include affected service, timestamp, log source, and error message.
        - Expand the log search window.
        - Check related metrics and infrastructure logs.
        """)