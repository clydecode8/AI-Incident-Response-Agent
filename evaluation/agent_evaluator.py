# agent/agent_evaluator.py
"""
Quality-oriented evaluator for the AI Incident Response Agent.

This evaluator focuses on whether the investigation is correct, grounded,
useful, and efficient. It does not require one fixed tool trajectory, because
real investigations may legitimately choose different paths.
"""

import json
import re
from collections import Counter
from evaluation.deepeval_evaluator import run_deepeval_incident_judge

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "this", "that", "it", "its",
    "as", "by", "from", "at", "not", "but", "if", "then", "than", "into",
    "due", "root", "cause", "summary", "recommendation", "recommendations",
    "incident", "investigation", "primary", "suspected", "observed",
    "anomalies", "status", "assessment", "action", "actions", "check",
    "review", "investigate", "further", "unclear", "possible", "likely",
    "appears", "related", "multiple", "occurred", "caused", "exact",
    "current", "final", "report", "provided", "include", "includes",
    "using", "used", "shows", "show", "found", "result", "results",
}

# Terms that are either generic infra vocabulary or reasonable remediation words.
# These should not be treated as hallucinated incident-specific facts.
IGNORED_GROUNDING_TERMS = {
    "search_logs", "search_error_logs", "search_metrics", "retrieve_knowledge",
    "search_codebase", "line", "lines", "fix", "remove",
    "remove/fix", "add", "validate", "retry", "restart", "monitor", "logging",
    "guard", "null", "handling", "fallback", "configuration", "config", "root",
    "cause", "remediation", "recommended", "actions", "next", "steps",
    "service", "services", "application", "system", "component", "logs", "log",
    "metrics", "metric", "error", "errors", "exception", "exceptions", "status",
    "source", "severity", "symptom", "environment", "process", "thread", "main",
    "broker", "cluster", "server", "queue", "gateway", "worker", "node", "job",
}


ROOT_CAUSE_RULES = [
    {
        "name": "Kafka Timeout",
        "signals": ["kafkatimeoutexception", "broker unavailable", "paymentservice", "payment event"],
        "required_any": ["kafkatimeoutexception", "broker unavailable", "kafka"],
        "support_any": ["paymentservice", "payment event", "publish", "broker"],
        "expected": "PaymentService failed to publish events because Kafka/broker was unavailable.",
    },
    {
        "name": "NullPointerException",
        "signals": ["nullpointerexception", "getemail", "userservice", "user is null"],
        "required_any": ["nullpointerexception", "getemail", "user object", "user is null", "null user"],
        "support_any": ["userservice", "welcome email", "id=1001", "getemail"],
        "expected": "UserService attempted to use a null User object and call getEmail().",
    },
    {
        "name": "Hadoop Job Failure",
        "signals": ["hadoop", "hdfs", "datanode", "namenode", "block replication"],
        "required_any": ["datanode", "hdfs", "block replication", "connection refused", "job failed"],
        "support_any": ["hadoop", "timeout", "slow", "job"],
        "expected": "Hadoop job failure related to DataNode/HDFS connection or block replication failure.",
    },
    {
        "name": "Linux Server Issue",
        "signals": ["linux", "authentication failure", "permission denied", "failed logins", "deploy"],
        "required_any": ["authentication failure", "permission denied", "failed logins", "service failed"],
        "support_any": ["linux", "deploy", "login", "permission"],
        "expected": "Linux issue related to authentication/permission failure or service start failure.",
    },
]


def normalize_action(action: str) -> str:
    action = (action or "").lower()

    if "code" in action:
        return "search_codebase"
    if "metric" in action:
        return "search_metrics"
    if "runbook" in action or "knowledge" in action:
        return "retrieve_knowledge"
    if "error_logs" in action or "log" in action:
        return "search_logs"

    return action


def normalize_report_text(report) -> str:
    """Unwrap nested report dictionaries or JSON strings into plain report text."""
    value = report

    for _ in range(5):
        if isinstance(value, dict):
            value = value.get("answer") or value.get("report") or value.get("content") or str(value)
            continue

        if isinstance(value, str):
            text = value.strip()
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    value = parsed
                    continue
            except Exception:
                return value

        return str(value)

    return str(value)

def evaluate_agent_run(alert_text: str, result: dict) -> dict:
    raw_report = result.get("report", "") if isinstance(result, dict) else str(result)
    report = normalize_report_text(raw_report)
    trace = result.get("trace", []) if isinstance(result, dict) else []

    actual_tools = [
        normalize_action(item.get("action", ""))
        for item in trace
        if isinstance(item, dict)
    ]

    recommended_tools = infer_recommended_tools(alert_text)

    sections = {
        "root_cause_accuracy": evaluate_root_cause_accuracy(alert_text, report),
        "evidence_completeness": evaluate_evidence_completeness(alert_text, trace, actual_tools),
        "grounding": evaluate_grounding(alert_text, report, trace),
        "investigation_efficiency": evaluate_investigation_efficiency(trace, actual_tools),
        "actionability": evaluate_actionability(report),
    }

    try:
        deepeval_result = run_deepeval_incident_judge(
            alert_text=alert_text,
            final_report=report,
            trace=trace,
        )

        sections["llm_judge_quality"] = {
            "passed": deepeval_result["passed"],
            "critical": False,
            "score": deepeval_result["score"],
            "reason": deepeval_result["reason"],
            "metric": deepeval_result["name"],
        }

    except Exception as e:
        sections["llm_judge_quality"] = {
            "passed": False,
            "critical": False,
            "score": 0.0,
            "reason": f"DeepEval judge failed: {e}",
        }

    weights = {
        "root_cause_accuracy": 25,
        "evidence_completeness": 20,
        "grounding": 20,
        "investigation_efficiency": 10,
        "actionability": 10,
        "llm_judge_quality": 15,
    }

    score = 0.0
    for name, section in sections.items():
        score += weights.get(name, 0) * float(section.get("score", 0.0))

    score = round(score, 2)
    passed = sum(1 for item in sections.values() if item.get("passed"))
    total = len(sections)

    critical_failures = [
        name for name, section in sections.items()
        if section.get("critical") and not section.get("passed")
    ]

    if critical_failures:
        overall = "FAIL"
    elif score >= 85:
        overall = "PASS"
    elif score >= 65:
        overall = "PARTIAL_PASS"
    else:
        overall = "FAIL"

    return {
        "framework": (
            "Hybrid evaluation using rule-based checks plus DeepEval LLM-as-a-Judge "
            "for incident report quality."
        ),
        "overall": overall,
        "score": score,
        "passed": passed,
        "total": total,
        "critical_failures": critical_failures,
        "recommended_tools": recommended_tools,
        "actual_tools": actual_tools,
        "expected_tools": recommended_tools,
        "sections": sections,
    }

def infer_incident_type(text: str) -> dict:
    lowered = (text or "").lower()

    best_rule = None
    best_score = 0

    for rule in ROOT_CAUSE_RULES:
        score = sum(1 for signal in rule["signals"] if signal in lowered)
        if score > best_score:
            best_score = score
            best_rule = rule

    return best_rule if best_score > 0 else None


def infer_recommended_tools(alert_text: str) -> list:
    text = (alert_text or "").lower()
    tools = ["search_logs"]

    is_app_exception = any(x in text for x in [
        "java.lang", "nullpointerexception", "runtimeexception",
        "kafkatimeoutexception", "userservice", "paymentservice",
    ])

    metrics_useful = any(x in text for x in [
        "latency", "slow", "cpu", "disk", "memory", "degraded",
        "failed_jobs", "failed logins", "timeout", "unavailable",
    ])

    if metrics_useful:
        tools.append("search_metrics")

    if is_app_exception:
        tools.append("search_codebase")

    # Runbook is useful but not mandatory; include as recommended, not a hard failure.
    if any(x in text for x in [
        "exception", "timeout", "failed", "failure", "refused",
        "denied", "error", "unavailable", "crash",
    ]):
        tools.append("retrieve_knowledge")

    return tools


def evaluate_root_cause_accuracy(alert_text: str, report: str) -> dict:
    alert_rule = infer_incident_type(alert_text)
    report_text = (report or "").lower()

    if not report_text.strip():
        return {
            "passed": False,
            "critical": True,
            "score": 0.0,
            "reason": "No final report was produced.",
        }

    fallback_phrases = [
        "could not reach a confirmed root cause",
        "insufficient evidence",
        "investigation incomplete",
        "not enough evidence",
    ]

    if any(phrase in report_text for phrase in fallback_phrases):
        return {
            "passed": False,
            "critical": True,
            "score": 0.0,
            "reason": "Report fell back to an incomplete/insufficient-evidence answer.",
        }

    if not alert_rule:
        has_reasonable_cause = any(x in report_text for x in [
            "root cause", "suspected", "caused by", "likely", "because",
        ])
        return {
            "passed": has_reasonable_cause,
            "critical": False,
            "score": 1.0 if has_reasonable_cause else 0.4,
            "reason": (
                "Report provides a plausible cause/assessment for an unknown incident type."
                if has_reasonable_cause else
                "Report does not clearly identify a cause or assessment."
            ),
        }

    required_hit = any(term in report_text for term in alert_rule["required_any"])
    support_hit = any(term in report_text for term in alert_rule["support_any"])

    if required_hit and support_hit:
        score = 1.0
        passed = True
        reason = f"Report identifies the expected root cause: {alert_rule['expected']}"
    elif required_hit:
        score = 0.7
        passed = True
        reason = "Report identifies the main failure signal but gives limited supporting context."
    else:
        score = 0.2
        passed = False
        reason = f"Report does not clearly identify expected root cause: {alert_rule['expected']}"

    return {
        "passed": passed,
        "critical": not passed,
        "score": score,
        "reason": reason,
        "incident_type": alert_rule["name"],
        "expected_root_cause": alert_rule["expected"],
    }


def evaluate_evidence_completeness(alert_text: str, trace: list, actual_tools: list) -> dict:
    text = (alert_text or "").lower()
    actual_set = set(actual_tools)

    required = ["search_logs"]
    optional = []

    is_app_exception = any(x in text for x in [
        "java.lang", "nullpointerexception", "runtimeexception",
        "kafkatimeoutexception", "userservice", "paymentservice",
    ])

    if is_app_exception:
        required.append("search_codebase")

    metrics_relevant = any(x in text for x in [
        "latency", "slow", "cpu", "disk", "memory", "degraded",
        "failed_jobs", "failed logins", "timeout", "unavailable",
    ])
    if metrics_relevant:
        optional.append("search_metrics")

    if any(x in text for x in [
        "exception", "timeout", "failed", "failure", "refused", "denied", "error", "unavailable"
    ]):
        optional.append("retrieve_knowledge")

    missing_required = [tool for tool in required if tool not in actual_set]
    used_optional = [tool for tool in optional if tool in actual_set]
    missing_optional = [tool for tool in optional if tool not in actual_set]

    required_score = 1.0 if not missing_required else max(0.0, 1 - len(missing_required) / len(required))
    optional_bonus = 0.0 if not optional else 0.15 * (len(used_optional) / len(optional))
    score = min(1.0, required_score * 0.85 + optional_bonus)

    passed = len(missing_required) == 0 and score >= 0.75

    return {
        "passed": passed,
        "critical": False,
        "score": round(score, 2),
        "reason": (
            "Required evidence sources were collected; optional sources are treated as bonus."
            if passed else
            f"Missing required evidence sources: {missing_required}"
        ),
        "required_tools": required,
        "optional_tools": optional,
        "used_optional_tools": used_optional,
        "missing_optional_tools": missing_optional,
        "actual_tools": actual_tools,
    }


def evaluate_grounding(alert_text: str, report: str, trace: list) -> dict:
    evidence_text = f"{alert_text or ''}\n{_trace_observations_text(trace)}"

    evidence_terms = _extract_key_terms(evidence_text)
    report_terms = _extract_key_terms(report)

    unsupported_terms = sorted([
        term for term in report_terms
        if term not in evidence_terms and term not in IGNORED_GROUNDING_TERMS
    ])

    # Minor unsupported remediation/general terms should not fail an otherwise grounded RCA.
    major_unsupported = [term for term in unsupported_terms if _looks_incident_specific(term)]

    if not report_terms:
        score = 0.0
    else:
        supported_count = len(report_terms) - len(major_unsupported)
        score = max(0.0, supported_count / len(report_terms))

    passed = len(major_unsupported) <= 2 and score >= 0.85

    return {
        "passed": passed,
        "critical": False,
        "score": round(score, 2),
        "reason": (
            "Final report is mostly grounded in the alert and tool observations."
            if passed else
            "Final report introduces unsupported incident-specific terms."
        ),
        "unsupported_terms": major_unsupported[:20],
        "evidence_terms_sample": sorted(list(evidence_terms))[:30],
        "report_terms_sample": sorted(list(report_terms))[:30],
    }


def evaluate_investigation_efficiency(trace: list, actual_tools: list) -> dict:
    calls = [
        (normalize_action(item.get("action", "")), str(item.get("input", "")).strip().lower())
        for item in trace
        if isinstance(item, dict)
    ]

    total_calls = len(calls)
    duplicate_calls = sum(count - 1 for count in Counter(calls).values() if count > 1)

    repeated_same_tool = 0
    for prev, current in zip(actual_tools, actual_tools[1:]):
        if prev == current:
            repeated_same_tool += 1

    if total_calls == 0:
        score = 0.0
    else:
        score = 1.0
        score -= min(0.5, duplicate_calls * 0.2)
        score -= min(0.3, repeated_same_tool * 0.1)
        if total_calls > 8:
            score -= min(0.2, (total_calls - 8) * 0.05)
        score = max(0.0, score)

    passed = score >= 0.7

    return {
        "passed": passed,
        "critical": False,
        "score": round(score, 2),
        "reason": (
            "Tool usage is efficient with little or no redundant repetition."
            if passed else
            "Tool usage contains repeated or excessive calls."
        ),
        "tool_call_count": total_calls,
        "duplicate_exact_calls": duplicate_calls,
        "repeated_same_tool_transitions": repeated_same_tool,
        "actual_tools": actual_tools,
    }


def evaluate_actionability(report: str) -> dict:
    text = (report or "").lower()

    has_action_section = any(x in text for x in [
        "recommended actions", "next actions", "remediation", "recommendation", "fix", "mitigation"
    ])

    specific_action_terms = [
        "add", "validate", "null check", "retry", "restart", "verify", "check",
        "review", "monitor", "rollback", "increase", "inspect", "confirm",
        "update", "handle", "guard", "alert", "logs", "metrics", "broker",
        "permission", "authentication", "datanode", "hdfs",
    ]

    action_hits = sorted({term for term in specific_action_terms if term in text})

    if has_action_section and len(action_hits) >= 2:
        score = 1.0
        passed = True
    elif len(action_hits) >= 2:
        score = 0.8
        passed = True
    elif len(action_hits) == 1:
        score = 0.5
        passed = False
    else:
        score = 0.2
        passed = False

    return {
        "passed": passed,
        "critical": False,
        "score": score,
        "reason": (
            "Report provides concrete next actions or remediation guidance."
            if passed else
            "Report does not provide enough concrete remediation guidance."
        ),
        "has_action_section": has_action_section,
        "action_terms_found": action_hits,
    }


def _trace_observations_text(trace: list) -> str:
    return "\n".join(
        str(item.get("observation", ""))
        for item in trace
        if isinstance(item, dict)
    )


def _extract_key_terms(text: str) -> set:
    text = text or ""

    # Remove dates, times, line ranges, and standalone numbers from grounding checks.
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}[t\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)
    text = re.sub(r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b", " ", text)
    text = re.sub(r"\b\d+\s*-\s*\d+\b", " ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", " ", text)

    terms = set()

    exception_terms = re.findall(
        r"\b[a-zA-Z][a-zA-Z0-9_]*(?:exception|error|timeout|failure)\b",
        text,
        flags=re.IGNORECASE,
    )
    terms.update(term.lower() for term in exception_terms)

    technical_names = re.findall(
        r"\b[A-Z][a-zA-Z0-9_]*(?:Service|Server|Cluster|Database|Queue|Broker|Cache|Gateway|Worker|Node|Job|API)\b",
        text,
    )
    terms.update(term.lower() for term in technical_names)

    structured_tokens = re.findall(
        r"\b[a-zA-Z0-9]+(?:[._\-:/][a-zA-Z0-9]+)+\b",
        text,
    )
    for token in structured_tokens:
        token = token.strip("._-:/").lower()
        if len(token) >= 4:
            terms.add(token)

    acronyms = re.findall(r"\b[A-Z]{2,}\b", text)
    terms.update(term.lower() for term in acronyms)

    infra_nouns = {
        "namenode", "datanode", "hdfs", "yarn", "kafka", "broker", "brokers",
        "paymentservice", "userservice", "hadoopcluster", "linuxserver",
        "authentication", "permission", "deploy", "getemail", "nullpointerexception",
        "kafkatimeoutexception", "runtimeexception", "filewriter", "metricsutil",
        "logutil", "incidentdemoapplication", "kafkaservice", "paymentservice",
        "userservice", "block", "replication", "latency", "degraded", "cpu", "disk",
    }

    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]{2,}\b", text.lower())
    for word in words:
        if word in infra_nouns:
            terms.add(word)

    return {
        term for term in terms
        if term not in STOPWORDS and term not in IGNORED_GROUNDING_TERMS
    }


def _looks_incident_specific(term: str) -> bool:
    if not term or term in IGNORED_GROUNDING_TERMS:
        return False

    # File/class/method names, exception names, protocol/system names are incident-specific.
    return any(marker in term for marker in [".", "_", "exception", "timeout", "service", "hdfs", "kafka", "datanode", "namenode"])
