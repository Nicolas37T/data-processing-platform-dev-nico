import sys
sys.path.insert(0, r'C:\Users\DATAX\Documents\Nicolas\Taiga\webhook_reader')

import paramiko
import json
import re

AIRFLOW_LOGS_BASE = "/home/datax-pds/datax/data-processing-platform-dev/logs"

def improved_extract_meaningful_log(raw_log: str, max_lines: int = 35) -> str:
    if not raw_log or not raw_log.strip():
        return ""

    lines = raw_log.strip().splitlines()
    extracted = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean.startswith("{") and line_clean.endswith("}"):
            try:
                obj = json.loads(line_clean)
                event = str(obj.get("event", ""))
                level = str(obj.get("level", "")).lower()
                logger = str(obj.get("logger", ""))

                if any(bp in event for bp in ["::group::", "::endgroup::", "DAG bundles loaded", "Filling up the DagBag"]):
                    continue

                if level == "error" or "error" in event.lower() or "fail" in event.lower():
                    extracted.append(f"[ERROR] {event}")
                    if "error_detail" in obj and obj["error_detail"]:
                        for err in obj["error_detail"]:
                            exc_type = err.get("exc_type", "Exception")
                            exc_val = err.get("exc_value", "")
                            extracted.append(f"{exc_type}: {exc_val}")
                            frames = err.get("frames", [])
                            for fr in frames[-5:]:
                                fn = fr.get("filename", "")
                                ln = fr.get("lineno", "")
                                name = fr.get("name", "")
                                extracted.append(f"  File \"{fn}\", line {ln}, in {name}")

                elif logger == "task.stdout" or level in ("info", "warn", "warning"):
                    # Check for keywords of interest in stdout/info
                    ev_lower = event.lower()
                    if any(k in ev_lower for k in [
                        "error:", "columns identified", "does not match", "there might be a change",
                        "comparing files", "structure verified", "extraction error", "exception",
                        "traceback", "value verification", "returned value was", "following branch"
                    ]):
                        extracted.append(event)
            except Exception:
                extracted.append(line_clean)
        else:
            extracted.append(line_clean)

    if not extracted:
        # Fallback to last N non-empty lines
        return "\n".join(lines[-max_lines:])

    return "\n".join(extracted[-max_lines:])


def improved_fetch_airflow_task_log(dag_code: str, task_id: str = None) -> str:
    candidates = []
    if task_id:
        candidates.append(task_id)

    if dag_code.startswith("C_"):
        for t in ["structure_review", "extraction", "read_file", "get_conversion_data"]:
            if t not in candidates: candidates.append(t)
    elif dag_code.startswith("D_"):
        for t in ["compare_files", "file_download", "get_file_url", "verify_download"]:
            if t not in candidates: candidates.append(t)
    elif dag_code.startswith("M_"):
        for t in ["pre_load", "load"]:
            if t not in candidates: candidates.append(t)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("10.0.0.16", port=22, username="datax-pds", password=".datax-pds*/$", timeout=5)

    captured_logs = []
    try:
        for cand in candidates:
            cmd = f"find {AIRFLOW_LOGS_BASE}/dag_id={dag_code} -type f -name '*.log' | grep -E 'task_id={cand}/' | sort -r | head -n 3"
            stdin, stdout, stderr = client.exec_command(cmd)
            log_files = stdout.read().decode().strip().splitlines()

            for lf in log_files:
                if not lf.strip(): continue
                stdin, stdout, stderr = client.exec_command(f"cat '{lf}' | tail -n 120")
                raw = stdout.read().decode('utf-8', errors='ignore')
                snippet = improved_extract_meaningful_log(raw)
                # Check if this snippet has real error content
                snip_lower = snippet.lower()
                has_error = any(k in snip_lower for k in ["error", "fail", "traceback", "does not match", "typeerror", "exception", "change in structure"])
                if has_error:
                    captured_logs.append(f"=== [Log de Airflow: {cand}] ===\n{snippet}")
                    break # got the error log for this candidate

            # If we found an error log for primary candidate, stop
            if captured_logs:
                break

        # If no error log found across candidates, fetch the latest log of the first candidate
        if not captured_logs and candidates:
            cand = candidates[0]
            cmd = f"find {AIRFLOW_LOGS_BASE}/dag_id={dag_code} -type f -name '*.log' | grep -E 'task_id={cand}/' | sort -r | head -n 1"
            stdin, stdout, stderr = client.exec_command(cmd)
            lf = stdout.read().decode().strip()
            if lf:
                stdin, stdout, stderr = client.exec_command(f"cat '{lf}' | tail -n 80")
                raw = stdout.read().decode('utf-8', errors='ignore')
                snippet = improved_extract_meaningful_log(raw)
                if snippet:
                    captured_logs.append(f"=== [Log de Airflow: {cand}] ===\n{snippet}")
    finally:
        client.close()

    return "\n\n".join(captured_logs) if captured_logs else "No se capturó log adicional."

print("Testing improved_fetch_airflow_task_log for C_BO_000000290 (structure_review):")
print(improved_fetch_airflow_task_log("C_BO_000000290", "structure_review")[:600])

print("\nTesting improved_fetch_airflow_task_log for D_BO_000000316 (compare_files):")
print(improved_fetch_airflow_task_log("D_BO_000000316", "compare_files")[:600])
