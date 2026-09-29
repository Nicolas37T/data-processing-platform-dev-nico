import os
import requests

TAIGA_INCIDENT_URL = os.environ.get("TAIGA_INCIDENT_URL", "http://10.0.0.16:5000/api/dag-incident")


def send_taiga_incident(
    dag_code: str,
    error_type: str = "pipeline_error",
    failed_task: str = None,
    anomaly_path: str = None,
    exception_msg: str = None,
    file_code: str = None,
    subreport_code: str = None,
    subreport_name: str = None,
    priority: str = "High"
) -> bool:
    """
    Envía un webhook HTTP síncrono y ultra-rápido al servicio taiga-webhook-reader
    para registrar de inmediato la Historia de Usuario en Taiga cuando ocurre un error en Airflow.
    
    Tolerante a fallos: Si el webhook reader no está disponible o da timeout,
    la ejecución del DAG de Airflow continúa normalmente sin interrumpirse.
    """
    try:
        payload = {
            "dag_code": dag_code,
            "error_type": error_type,
            "failed_task": failed_task or "",
            "anomaly_path": anomaly_path or "",
            "log_content": exception_msg or "",
            "file_code": file_code,
            "subreport_code": subreport_code,
            "subreport_name": subreport_name,
            "priority": priority
        }
        resp = requests.post(TAIGA_INCIDENT_URL, json=payload, timeout=3)
        print(f"[TAIGA_NOTIFIER] Incidente enviado para {dag_code} ({failed_task or error_type}) -> Status: {resp.status_code}")
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[TAIGA_NOTIFIER] Aviso: No se pudo enviar webhook a Taiga para {dag_code}: {e}")
        return False
