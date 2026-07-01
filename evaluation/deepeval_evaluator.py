from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import GEval
import json

from evaluation.gemini_deepeval_model import GeminiDeepEvalLLM
from evaluation.groq_deepeval_model import GroqDeepEvalLLM

def get_judge_model():

    with open("runtime/llm_config.json") as f:
        provider = json.load(f)["provider"]

    if provider == "groq":
        return GeminiDeepEvalLLM()

    return GroqDeepEvalLLM()

judge_model = get_judge_model()

def run_deepeval_incident_judge(alert_text: str, final_report: str, trace: list, judge_model):
    tools_used = [
        item.get("action", "")
        for item in trace
        if isinstance(item, dict)
    ]

    observations = "\n\n".join(
        str(item.get("observation", ""))
        for item in trace
        if isinstance(item, dict)
    )

    test_case = LLMTestCase(
        input=f"""
Alert:
{alert_text}

Tools Used:
{tools_used}

Tool Observations:
{observations}
""",
        actual_output=final_report,
    )

    incident_quality_metric = GEval(
        name="Incident Response Quality",
        criteria="""
            Evaluate the incident report as an AI Site Reliability Engineer.

            Score based on:
            1. Root cause accuracy
            2. Evidence support from logs, metrics, codebase, or knowledge retrieval
            3. Grounding and faithfulness
            4. Actionability of remediation steps
            5. Whether unrelated incidents are separated instead of merged
            6. Whether retrieved knowledge was used if available

            Give a low score if the report invents facts, merges unrelated issues, or gives vague remediation.
        """,
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=judge_model,
        threshold=0.7,
    )

    incident_quality_metric.measure(test_case)

    return {
        "name": incident_quality_metric.name,
        "score": round(float(incident_quality_metric.score), 2),
        "passed": bool(incident_quality_metric.is_successful()),
        "reason": incident_quality_metric.reason,
    }