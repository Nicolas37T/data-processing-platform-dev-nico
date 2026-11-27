#!/usr/bin/env python3
"""Script para Reparar Desfases y Duplicados en Migración (PostgreSQL).

Limpia registros duplicados generados por ejecuciones concurrentes en
DATA_DB_<PAIS> y re-dispara el DAG de migración en Airflow con la configuración
exacta del último archivo SQLite consolidado.
"""

import json
import sys
import paramiko

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SERVER_HOST = "10.0.0.16"
SERVER_USER = "datax-pds"
SERVER_PASS = ".datax-pds*/$"


def reparar_migracion(report_code: str):
    print("=" * 70)
    print(f"🚚 REPARADOR DE MIGRACIÓN PARA: {report_code}")
    print("=" * 70)

    country = report_code.split("_")[1]
    dag_base = "_".join(report_code.split("_")[:-1])
    dag_migr = f"M_{dag_base[2:]}"  # ej. M_BO_000000538

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            SERVER_HOST,
            port=22,
            username=SERVER_USER,
            password=SERVER_PASS,
            timeout=5,
        )
    except Exception as e:
        print(f"❌ Error al conectar por SSH a {SERVER_HOST}: {e}")
        return

    # 1. Obtener storage_table y load_scope de platform_db
    cmd_info = f"""docker exec data-processing-platform-dev-postgres-1 psql -U postgres -d platform_db -t -A -c "
        SELECT storage_table || '|' || COALESCE(load_scope, '') FROM report WHERE code = '{report_code}';
    " """
    stdin, stdout, stderr = client.exec_command(cmd_info)
    info_out = stdout.read().decode().strip()

    if not info_out or ";" not in info_out:
        print(
            f"❌ No se encontró storage_table para {report_code} en platform_db"
        )
        client.close()
        return

    storage_table, load_scope = info_out.split("|")
    schema, table = storage_table.split(";")
    print(f"📋 Tabla Destino: \"{schema}\".\"{table}\" en DATA_DB_{country} (Scope: '{load_scope}')")

    # 2. Localizar el último archivo SQLite (priorizando archivos con fecha YYYY-MM-DD)
    cmd_find = f"""docker exec data-processing-platform-dev-airflow-worker-1 bash -c '
        LATEST=$(find /mnt/datos1/data_process/{country}/{dag_base}/ -name "[0-9]*_{report_code}.sqlite" | sort | tail -n 1)
        if [ -z "$LATEST" ]; then
            find /mnt/datos1/data_process/{country}/{dag_base}/ -name "*{report_code}.sqlite" | sort | tail -n 1
        else
            echo "$LATEST"
        fi
    '"""
    stdin, stdout, stderr = client.exec_command(cmd_find)
    last_sqlite = stdout.read().decode().strip()

    if not last_sqlite:
        print(
            f"❌ No se encontró archivo SQLite para {report_code} en data_process"
        )
        client.close()
        return

    print(f"📂 Último SQLite Detectado: {last_sqlite}")

    # 3. Limpiar tabla solo si el scope es acumulativo 'all', o dejar que pre_load gestione el rango
    if load_scope.strip().lower() == "all":
        cmd_clean = f"""docker exec data-processing-platform-dev-postgres-1 psql -U postgres -d DATA_DB_{country} -c "
            DELETE FROM \\"{schema}\\".\\"{table}\\";
        " """
        stdin, stdout, stderr = client.exec_command(cmd_clean)
        print(f"🧹 Limpieza total (scope=all): {stdout.read().decode().strip()}")
    else:
        print(f"ℹ️ Scope no es 'all'; la limpieza por rango de fechas la realizará pre_load en Airflow.")

    # 4. Disparar Migración en Airflow
    conf = json.dumps(
        {
            "code": report_code,
            "conversion_path": last_sqlite,
            "id_conversion": 1,
        }
    )
    cmd_trigger = f"""docker exec data-processing-platform-dev-airflow-worker-1 airflow dags trigger {dag_migr} --conf '{conf}'"""
    print(f"🚀 Disparando DAG: {dag_migr}...")
    stdin, stdout, stderr = client.exec_command(cmd_trigger)
    print(f"Salida de Airflow:\n{stdout.read().decode().strip()}")

    client.close()
    print("=" * 70)
    print(
        f"✅ Migración disparada para {report_code}. Verificar estado en el monitor en unos segundos."
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python reparar_desfase_migracion.py <CODIGO_REPORTE>")
        print("Ejemplo: python reparar_desfase_migracion.py D_BO_000000538_01")
        sys.exit(1)

    reparar_migracion(sys.argv[1])
