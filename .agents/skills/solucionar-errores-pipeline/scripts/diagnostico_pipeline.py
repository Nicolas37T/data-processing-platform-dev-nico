#!/usr/bin/env python3
"""Script de Diagnóstico Rápido para Pipelines DATAX.

Consulta el Pipeline Monitor y Taiga para generar un reporte instantáneo de
errores activos, desfases y tareas fallidas.
"""

import json
import sys
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MONITOR_URL = "http://10.0.0.16:8090/api"
TAIGA_URL = "http://10.0.0.16:5000/api/v1"


def diagnosticar(country: str = "BO"):
    print("=" * 70)
    print(f"📊 DIAGNÓSTICO DE PIPELINE - PAÍS: {country}")
    print("=" * 70)

    # 1. Consultar Monitor
    try:
        r = requests.get(f"{MONITOR_URL}/audit?country={country}", timeout=6)
        if r.status_code != 200:
            print(f"⚠️ Error al conectar con monitor: HTTP {r.status_code}")
            return
        data = r.json()
    except Exception as e:
        print(f"❌ Error al consultar Pipeline Monitor en {MONITOR_URL}: {e}")
        return

    kpi = data.get("kpi", {})
    print(f"\n📈 KPIs de Plataforma:")
    print(
        f"   Total Robots: {kpi.get('total_robots')} | Sincronizados: {kpi.get('synced')} | Con Desfase: {kpi.get('lagged')} | Errores: {kpi.get('errors')}"
    )

    robots = data.get("robots", [])
    anomalias = []
    for rb in robots:
        status = rb.get("overall_status")
        is_desfase = rb.get("is_desfase")
        has_error = rb.get("has_error")
        struct_errors = rb.get("active_structure_errors", [])
        exceptions = rb.get("active_exceptions", [])

        if (
            status in ("ERROR", "LAGGED")
            or is_desfase
            or has_error
            or struct_errors
            or exceptions
        ):
            anomalias.append(rb)

    if not anomalias:
        print(
            "\n✅ ¡Todo despejado! No hay robots con errores ni desfases activos."
        )
        return

    print(f"\n🚨 Se detectaron {len(anomalias)} robots con observaciones:")
    for rb in anomalias:
        code = rb.get("code")
        name = rb.get("name")
        status = rb.get("overall_status")
        print(f"\n🔹 [{code}] - {name}")
        print(f"   Estado General: {status}")
        print(
            f"   Fechas: Descarga: {rb.get('download_date')} | Conv: {rb.get('conversion_date')} | Migr: {rb.get('migration_date')}"
        )

        lag_reasons = rb.get("lag_reasons", [])
        if lag_reasons:
            print(f"   Motivos de Lag: {', '.join(lag_reasons)}")

        struct_errors = rb.get("active_structure_errors", [])
        if struct_errors:
            print(
                f"   ⚠️ Anomalías de Estructura Activas ({len(struct_errors)}):"
            )
            for se in struct_errors:
                print(
                    f"      - Carpeta: {se.get('folder')} (Subreportes: {se.get('affected_subreports')})"
                )

        exceptions = rb.get("active_exceptions", [])
        if exceptions:
            print(f"   ⚠️ Excepciones Registradas ({len(exceptions)}):")
            for exc in exceptions:
                print(
                    f"      - Tarea: {exc.get('failed_task')} | Error: {exc.get('exceptions')}"
                )

        print("   Subreportes:")
        for sr in rb.get("subreports", []):
            print(
                f"      * {sr.get('code')}: status={sr.get('status')} | conv_to={sr.get('converted_to')} | migr_to={sr.get('migrated_to')}"
            )

    print("\n" + "=" * 70)


if __name__ == "__main__":
    country = sys.argv[1] if len(sys.argv) > 1 else "BO"
    diagnosticar(country)
