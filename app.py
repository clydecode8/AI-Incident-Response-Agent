import os
import json
import glob
import subprocess
import streamlit as st

from datetime import datetime
from agent.react_agent import run_react_agent
from tools.elastic_logs import ingest_log_file
from agent.incident_monitor import alert_to_text
from agent.alert_store import list_alerts, update_alert_status, clear_alerts

JAVA_DIR = "incident-demo"
MAIN_CLASS = "com.incident.incident_demo.IncidentDemoApplication"

TEST_CASES = {
    "Kafka Timeout": {
        "scenario": "kafka",
        "log_source": "application",
        "service": "PaymentService",
        "severity": "P2",
        "error": "KafkaTimeoutException",
        "symptom": "Payment event publishing failed",
        "alert": """P2 Alert

Service: PaymentService
Environment: Local Demo
Log Source: application
Symptom: Payment event publishing failed
Possible Error: KafkaTimeoutException
"""
    },
    "NullPointerException": {
        "scenario": "null-user",
        "log_source": "application",
        "service": "UserService",
        "severity": "P2",
        "error": "NullPointerException",
        "symptom": "Welcome email flow failed",
        "alert": """P2 Alert

Service: UserService
Environment: Local Demo
Log Source: application
Symptom: Welcome email flow failed
Possible Error: NullPointerException
"""
    },
    "Hadoop Job Failure": {
        "scenario": "none",
        "log_source": "hadoop",
        "service": "Hadoop Cluster",
        "severity": "P2",
        "error": "DataNode / HDFS failure",
        "symptom": "Hadoop jobs are failing",
        "alert": """Production Alert

Service: Hadoop Cluster
Environment: Local Demo
Log Source: hadoop
Symptom: Hadoop jobs are failing and users report slow execution.
Possible Error: DataNode connection refused / HDFS timeout
"""
    },
    "Linux Server Issue": {
        "scenario": "none",
        "log_source": "linux",
        "service": "Linux Server",
        "severity": "P2",
        "error": "Authentication / permission issue",
        "symptom": "Linux server instability",
        "alert": """Production Alert

Service: Linux Server
Environment: Local Demo
Log Source: linux
Symptom: Users report login failures, permission issues, or service instability.
Possible Error: authentication failure / permission denied / service failed
"""
    }
}

MANUAL_HISTORY_PATH = "runtime/manual_history.json"

def load_manual_history():
    if not os.path.exists(MANUAL_HISTORY_PATH):
        return []

    try:
        with open(MANUAL_HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_manual_history(history):
    os.makedirs("runtime", exist_ok=True)

    with open(MANUAL_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def start_background_process(script_name: str):
    os.makedirs("runtime", exist_ok=True)

    log_path = f"runtime/{script_name}.log"

    with open(log_path, "a", encoding="utf-8") as log_file:
        subprocess.Popen(
            ["python", script_name],
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        )

    return log_path

def load_services_config():
    path = "runtime/services_config.json"
    default = {
        "monitor_enabled": False,
        "auto_investigator_enabled": False,
    }

    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return {**default, **json.load(f)}
    except Exception:
        return default


def save_services_config(config):
    os.makedirs("runtime", exist_ok=True)
    with open("runtime/services_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def ingest_selected_source(log_source: str):
    path = f"incident-demo/logs/{log_source}.log"
    ingest_log_file(path, log_source)

def run_java_scenario(scenario: str):
    if scenario == "none":
        return True, "No Java scenario selected. Using existing logs only."

    source_pattern = os.path.join(
        "src", "main", "java", "com", "incident", "incident_demo", "*.java"
    )
    java_files = glob.glob(os.path.join(JAVA_DIR, source_pattern))

    if not java_files:
        return False, "No Java source files found."

    os.makedirs(os.path.join(JAVA_DIR, "target", "classes"), exist_ok=True)

    compile_cmd = [
        "javac",
        "-d",
        os.path.join("target", "classes"),
        *[os.path.relpath(file, JAVA_DIR) for file in java_files]
    ]

    run_cmd = [
        "java",
        "-cp",
        os.path.join("target", "classes"),
        MAIN_CLASS,
        scenario
    ]

    compile_result = subprocess.run(
        compile_cmd,
        cwd=JAVA_DIR,
        capture_output=True,
        text=True
    )

    if compile_result.returncode != 0:
        return False, (compile_result.stdout or "") + (compile_result.stderr or "")

    run_result = subprocess.run(
        run_cmd,
        cwd=JAVA_DIR,
        capture_output=True,
        text=True
    )

    output = (run_result.stdout or "") + (run_result.stderr or "")
    return True, output if output.strip() else "Java scenario executed."

def get_monitor_worker_status():
    status_path = "runtime/monitor_status.json"

    if not os.path.exists(status_path):
        return {
            "running": False,
            "message": "Monitor worker not detected.",
            "updated_at": None,
        }

    try:
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)

        updated_at = status.get("updated_at")

        if not updated_at:
            return {
                "running": False,
                "message": "Monitor worker status file exists but has no timestamp.",
                "updated_at": None,
            }

        updated_time = datetime.fromisoformat(updated_at)
        age_seconds = (datetime.now() - updated_time).total_seconds()

        if age_seconds <= 10:
            return {
                "running": True,
                "message": f"Monitor worker is running. Last heartbeat {age_seconds:.1f}s ago.",
                "updated_at": updated_at,
            }

        return {
            "running": False,
            "message": f"Monitor worker may be stopped. Last heartbeat {age_seconds:.1f}s ago.",
            "updated_at": updated_at,
        }

    except Exception as e:
        return {
            "running": False,
            "message": f"Could not read monitor worker status: {e}",
            "updated_at": None,
        }
    
def clear_demo_logs():
    for path in [
        "incident-demo/logs/application.log",
        "incident-demo/logs/hadoop.log",
        "incident-demo/logs/linux.log",
    ]:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("")

    with open("incident-demo/metrics/metrics.json", "w", encoding="utf-8") as f:
        json.dump({}, f)

    from tools.elastic_logs import get_es_client, INDEX_NAME

    es = get_es_client()
    if es is not None and es.indices.exists(index=INDEX_NAME):
        es.delete_by_query(
            index=INDEX_NAME,
            query={"match_all": {}},
            refresh=True
        )


def inject_selected_incident(selected_case_name: str):
    case = TEST_CASES[selected_case_name]

    if selected_case_name in ["Kafka Timeout", "NullPointerException"]:
        success, output = run_java_scenario(case["scenario"])

        if not success:
            return False, output

        ingest_log_file("incident-demo/logs/application.log", "application")
        return True, output
    
    elif selected_case_name == "Hadoop Job Failure":
        append_log(
            "hadoop",
            "2026-06-30 14:30:00 ERROR HadoopCluster - DataNode connection refused. HDFS block replication failed. Job failed due to timeout."
        )
        return True, "Injected Hadoop log into Elasticsearch."
    
    elif selected_case_name == "Linux Server Issue":
        append_log(
            "linux",
            "2026-06-30 14:35:00 ERROR LinuxServer - authentication failure and permission denied for user deploy. Service failed to start."
        )
        return True, "Injected Linux log into Elasticsearch."

def append_log(log_source: str, line: str):
    os.makedirs("incident-demo/logs", exist_ok=True)
    path = f"incident-demo/logs/{log_source}.log"

    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + line + "\n")

    ingest_log_file(path, log_source)

def display_detected_alert(alert: dict, show_evidence: bool = True):
    st.markdown(f"""
        **Source:** `{alert.get("source")}`  
        **Log Source:** `{alert.get("log_source")}`  
        **Service:** `{alert.get("service")}`  
        **Severity:** `{alert.get("severity")}`  
        **Symptom:** {alert.get("symptom")}  
        **Detected Pattern:** `{alert.get("detected_pattern")}`  
        **Timestamp:** `{alert.get("timestamp")}`
    """)

    if show_evidence:
        st.markdown("**Raw Evidence**")
        st.code(alert.get("raw_evidence", ""), language="text")

def get_report_text(report):
    if not report:
        return "No report generated."

    for _ in range(5):  # unwrap nested dict/json safely
        if isinstance(report, dict):
            report = (
                report.get("answer")
                or report.get("report")
                or report.get("content")
                or str(report)
            )
            continue

        if isinstance(report, str):
            text = report.strip()

            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    report = parsed
                    continue
            except Exception:
                return report

        return str(report)

    return str(report)

def normalize_result(result):
    if isinstance(result, dict):
        return result

    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}

    return {}

def display_agent_evaluation(result, allow_expanders=True):
    result = normalize_result(result)

    if not result:
        return

    evaluation = result.get("evaluation")

    if not evaluation:
        st.warning("No evaluation found in this report object.")
        return

    st.divider()
    st.subheader("Agent Evaluation")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Overall", evaluation.get("overall", "N/A"))

    with c2:
        st.metric("Score", f'{evaluation.get("score", 0)}%')

    with c3:
        st.metric("Passed", f'{evaluation.get("passed", 0)}/{evaluation.get("total", 0)}')

    st.caption(evaluation.get("framework", ""))

    st.markdown("### Evidence Sources Used")
    st.write("**Tools Used:**")
    st.code(" → ".join(evaluation.get("actual_tools", [])) or "None")

    st.markdown("### Evaluation Sections")

    for name, section in evaluation.get("sections", {}).items():
        icon = "✅" if section.get("passed") else "❌"
        title = f"{icon} {name.replace('_', ' ').title()}"

        if allow_expanders:
            with st.expander(title):
                st.write(section.get("reason", ""))

                extra = {
                    k: v for k, v in section.items()
                    if k not in ["passed", "reason"]
                }

                if extra:
                    st.json(extra)
        else:
            st.markdown(f"**{title}**")
            st.write(section.get("reason", ""))

            extra = {
                k: v for k, v in section.items()
                if k not in ["passed", "reason"]
            }

            if extra:
                st.json(extra)

st.set_page_config(
    page_title="AI Incident Response Agent",
    layout="wide"
)

st.title("🚨 AI Incident Response Agent")
st.caption(
    "ReAct-style AI SRE agent with background monitoring, manual alert investigation, "
    "log analysis, metrics, and runbook-based RCA."
)

if "result" not in st.session_state:
    st.session_state.result = None

if "java_output" not in st.session_state:
    st.session_state.java_output = ""

if "last_log_positions" not in st.session_state:
    st.session_state.last_log_positions = {
        "application": 0,
        "hadoop": 0,
        "linux": 0,
    }

if "selected_case_name" not in st.session_state:
    st.session_state.selected_case_name = None

if "monitor_enabled" not in st.session_state:
    st.session_state.monitor_enabled = False

if "last_detected_alert" not in st.session_state:
    st.session_state.last_detected_alert = None

if "display_alert" not in st.session_state:
    st.session_state.display_alert = None

if "incident_history" not in st.session_state:
    st.session_state.incident_history = []

if "monitor_message" not in st.session_state:
    st.session_state.monitor_message = "Background monitor is stopped."

if "manual_history" not in st.session_state:
    st.session_state.manual_history = load_manual_history()

st.sidebar.title("Incident Control Panel")

selected_case_name = st.sidebar.selectbox(
    "Choose demo incident",
    list(TEST_CASES.keys())
)


GEMINI_CHAT_ENABLED = os.getenv("GEMINI_CHAT_ENABLED", "false").lower() == "true"
GEMINI_EMBEDDING_ENABLED = os.getenv("GEMINI_EMBEDDING_ENABLED", "true").lower() == "true"

LLM_OPTIONS = {
    "Groq (LLAMA 3.3 70B Versatile)": "groq",
}

if GEMINI_CHAT_ENABLED:
    LLM_OPTIONS["Gemini 2.5 Flash"] = "gemini"

config_path = "runtime/llm_config.json"

# Default provider
provider = "groq"

# Read previously selected provider
if os.path.exists(config_path):
    try:
        with open(config_path, "r") as f:
            provider = json.load(f).get("provider", "groq")
    except Exception:
        provider = "groq"

# Determine which option should be selected
default_index = 0 if provider == "groq" else 1

# Show the dropdown
selected = st.sidebar.selectbox(
    "LLM Provider",
    list(LLM_OPTIONS.keys()),
    index=default_index
)

# Convert UI text into internal value
provider = LLM_OPTIONS[selected]

# Save to session
st.session_state.llm_provider = provider

# Save to file
os.makedirs("runtime", exist_ok=True)

with open(config_path, "w") as f:
    json.dump({"provider": provider}, f)

case = TEST_CASES[selected_case_name]

if st.session_state.selected_case_name != selected_case_name:
    st.session_state.result = None
    st.session_state.java_output = ""
    st.session_state.last_detected_alert = None
    st.session_state.selected_case_name = selected_case_name

st.sidebar.divider()
st.sidebar.subheader("Selected Incident")
st.sidebar.metric("Severity", case["severity"])
st.sidebar.markdown(f"""
**Service:** `{case["service"]}`  
**Log Source:** `{case["log_source"]}`  
**Possible Error:** `{case["error"]}`  
**Symptom:** {case["symptom"]}
""")

st.sidebar.divider()

st.sidebar.divider()
st.sidebar.subheader("Quick Actions")

if st.sidebar.button("Clear Demo Logs", use_container_width=True):
    clear_demo_logs()
    st.session_state.last_log_positions = {
        "application": 0,
        "hadoop": 0,
        "linux": 0,
    }
    st.session_state.result = None
    st.session_state.java_output = ""
    st.session_state.last_detected_alert = None
    st.session_state.display_alert = None
    st.sidebar.success("Logs cleared.")

if st.sidebar.button("Clear Alert Queue", use_container_width=True):
    clear_alerts()
    st.session_state.result = None
    st.session_state.java_output = ""
    st.sidebar.success("Alert queue cleared.")

st.sidebar.divider()
if "skip_next_monitor_cycle" not in st.session_state:
    st.session_state.skip_next_monitor_cycle = False

if "pending_injected_incident" not in st.session_state:
    st.session_state.pending_injected_incident = False

mode_tab, manual_tab, result_tab = st.tabs([
    "Auto Monitoring Demo",
    "Manual Alert Investigation",
    "Results"
])


with mode_tab:
    st.header("Auto Monitoring Demo")

    st.info(
        "Run `python monitor_worker.py` in a separate terminal. "
        "Then inject logs here. The worker will detect logs and create alerts automatically."
    )

    selected_source = case["log_source"]

    c1, c2, c3 = st.columns(3)

    with c1:
        
        st.subheader("1. Monitor Worker")

        worker_status = get_monitor_worker_status()

        if worker_status["running"]:
            st.success(worker_status["message"])
        else:
            st.error(worker_status["message"])
            st.code("python monitor_worker.py", language="bash")

        st.caption("This must run in a separate terminal.")

    with c2:
        st.subheader("2. Inject Log")
        if st.button("Inject Incident Log", use_container_width=True):
            success, output = inject_selected_incident(selected_case_name)
            st.session_state.java_output = output

            if success:
                st.success("Incident injected and indexed into Elasticsearch.")
            else:
                st.error("Incident injection failed.")
                st.code(output)

            st.session_state.java_output = (
                f"Injected incident log for: {selected_case_name}\n"
                f"Log Source: {case['log_source']}\n"
                f"Service: {case['service']}\n"
                f"Symptom: {case['symptom']}\n"
                f"Possible Error: {case['error']}"
            )

            st.success("Incident log injected. Worker will detect it automatically.")

    with c3:
        st.subheader("3. Alert Queue")
        st.write("New alerts appear below automatically.")
        
    st.divider()

    st.header("Alert Queue")

    alerts = list_alerts()

    if not alerts:
        st.info("No alerts yet. Inject an incident log.")
    else:
        for alert in alerts:
            alert_id = alert.get("id")
            status = alert.get("status", "NEW")

            with st.expander(
                f"[{status}] {alert.get('service')} - {alert.get('symptom')}",
                expanded=status in ["NEW", "INVESTIGATING"]
            ):
                display_detected_alert(alert, show_evidence=True)

                if status == "NEW":
                    if st.button(
                        f"Investigate Alert {alert_id}",
                        key=f"investigate_{alert_id}",
                        use_container_width=True
                    ):
                        update_alert_status(alert_id, "INVESTIGATING")
                        alert_text = alert_to_text(alert)

                        with st.spinner("AI agent is investigating..."):
                            result = run_react_agent(alert_text, st.session_state.llm_provider)

                        update_alert_status(alert_id, "RESOLVED", report=result)
                        st.session_state.result = result
                        st.success("Investigation completed.")

                elif status == "RESOLVED":
                    report = alert.get("report")
                    if report:
                        st.markdown("### AI Incident Report")
                        st.markdown(get_report_text(report))
                        display_agent_evaluation(report, allow_expanders=False)

    st.divider()

    st.subheader("How it works")
    st.markdown("""
        1. The app injects logs into the selected source.
        2. The monitor scans logs and creates a structured alert.
        3. The alert is stored in an alert queue.
        4. The AI agent investigates alerts from the queue.
        5. The final report is saved back to the resolved alert.
    """)


with manual_tab:
    st.header("Manual Alert Investigation")

    st.write(
        "Use this when an operator wants to paste an alert from Slack, PagerDuty, "
        "Grafana, CloudWatch, email, or a support ticket."
    )

    custom_alert = st.text_area(
        "Paste or edit alert",
        value=case["alert"].strip(),
        height=220
    )


    if st.button("Run & Analyze"):
        with st.spinner("AI agent is investigating user-submitted alert..."):
            report = run_react_agent(custom_alert, provider)

            st.session_state.result = report

            manual_item = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "Manual User Input",
                "alert_text": custom_alert,
                "report": report,
            }

            st.session_state.manual_history.insert(0, manual_item)
            save_manual_history(st.session_state.manual_history)

        st.success("Manual alert investigated and saved.")

with result_tab:
    st.header("Investigation Results")

    trace_tab, report_tab, resolved_tab, manual_result_tab = st.tabs([
        "Latest Agent Trace",
        "Latest Incident Report",
        "Resolved Alert Queue",
        "Manual Investigations"
    ])

    with trace_tab:
        result = st.session_state.result

        if not result:
            st.info("No latest in-session agent trace yet.")
        else:
            trace = result.get("trace", [])

            if not trace:
                st.warning("No tool calls recorded.")
            else:
                st.metric("Tool Calls", len(trace))

                for item in trace:
                    with st.expander(
                        f"Step {item['step']}: {item['action']}",
                        expanded=False
                    ):
                        st.markdown("**Tool Input**")
                        st.code(item.get("input") or "No input", language="text")

                        st.markdown("**Tool Observation**")
                        st.code(
                            item.get("observation", "No observation"),
                            language="text"
                        )

    with report_tab:
        result = st.session_state.result

        if result:
            st.markdown(get_report_text(result))
            display_agent_evaluation(result)
        else:
            resolved_alerts = [
                alert for alert in list_alerts()
                if alert.get("status") == "RESOLVED" and alert.get("report")
            ]

            if not resolved_alerts:
                st.info("No latest report yet.")
            else:
                latest = resolved_alerts[0]
                latest_report = latest.get("report")
                st.caption(
                    f"Showing latest resolved alert: "
                    f"{latest.get('service')} - {latest.get('created_at')}"
                )
                st.markdown(get_report_text(latest_report))
                display_agent_evaluation(latest_report)

    with resolved_tab:
        resolved_alerts = [
            alert for alert in list_alerts()
            if alert.get("status") == "RESOLVED"
        ]

        if not resolved_alerts:
            st.info("No resolved alerts yet.")
        else:
            st.metric("Resolved Alerts", len(resolved_alerts))

            for alert in resolved_alerts:
                report = alert.get("report", {})

                with st.expander(
                    f"{alert.get('created_at')} | "
                    f"{alert.get('service')} | "
                    f"{alert.get('symptom')}",
                    expanded=False
                ):
                    display_detected_alert(alert, show_evidence=False)

                    st.markdown("### Raw Evidence")
                    st.code(alert.get("raw_evidence", ""), language="text")

                    st.markdown("### AI Incident Report")
                    st.markdown(get_report_text(report))
                    display_agent_evaluation(report, allow_expanders=False)

                    trace = report.get("trace", [])

                    if trace:
                        st.markdown("### Agent Trace")
                        for item in trace:
                            st.markdown(
                                f"**Step {item['step']}: {item['action']}**"
                            )
                            st.code(
                                item.get("input") or "No input",
                                language="text"
                            )
                            
    with manual_result_tab:
        st.header("Manual User-Submitted Investigations")

        if not st.session_state.manual_history:
            st.info("No manual investigations yet.")
        else:
            for item in st.session_state.manual_history:
                with st.expander(
                    f'{item["time"]} | Manual User Input',
                    expanded=False
                ):
                    st.markdown("### User-Submitted Alert")
                    st.code(item["alert_text"], language="text")

                    st.markdown("### AI Incident Report")
                    st.markdown(get_report_text(item["report"]))
                    display_agent_evaluation(item["report"], allow_expanders=False)