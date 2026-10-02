---
name: solucionar-errores-pipeline
description: Playbook integral y automatizado para diagnosticar, clasificar, reparar y verificar errores en los pipelines de DATAX (Descarga, Conversión, Migración, Monitor y Taiga).
---

# 🛠️ Skill: Solucionador de Errores de Pipelines DATAX

Esta skill proporciona el procedimiento paso a paso para diagnosticar, clasificar y resolver incidentes en los robots y DAGs de **Descarga**, **Conversión** y **Migración**, garantizando la sincronización en el **Pipeline Monitor** y el cierre de incidencias en **Taiga**.

---

## ⚡ 1. Diagnóstico Rápido en 3 Pasos

### Paso 1: Consultar el Pipeline Monitor API
El backend del monitor corre en `http://10.0.0.16:8090/api`.
```python
import requests
res = requests.get("http://10.0.0.16:8090/api/audit?country=BO").json()

# Identificar robots con fallas o desfases
for rb in res.get("robots", []):
    if rb.get("overall_status") in ("ERROR", "LAGGED") or rb.get("is_desfase") or rb.get("has_error"):
        print(f"[{rb['code']}] Status: {rb.get('overall_status')} | Lag: {rb.get('lag_reasons')}")
```

### Paso 2: Revisar Incidentes Abiertos en Taiga
```python
import requests, sys
# Taiga API en http://10.0.0.16:5000/api/v1 o vía webhook container
# Buscar US en proyecto 9 con status=50 (New)
```

### Paso 3: Inspeccionar el Log en el Contenedor Airflow
Conectar vía SSH a `10.0.0.16` (`datax-pds`) e inspeccionar el log de la tarea fallida:
```bash
docker exec data-processing-platform-dev-airflow-worker-1 bash -c '
find /opt/airflow/logs/dag_id=<DAG_ID> -name "*.log" | sort | tail -n 5
'
```

---

## 🎯 2. Runbook de Resolución por Tipo de Error

### Caso A: Falso "Structure Change" (`no such table: columns_to_review`)
* **Síntoma:** Tarea `structure_review` falla con:
  ```text
  pandas.errors.DatabaseError: Execution failed on sql 'SELECT * FROM columns_to_review': no such table: columns_to_review
  ```
* **Solución:**
  1. Abrir el archivo SQLite consolidado previo (`/mnt/datos1/data_process/.../<fecha>_<subreporte>.sqlite`).
  2. Inyectar la tabla `columns_to_review` con la lista de niveles jerárquicos:
     ```python
     import sqlite3, pandas as pd
     cols = ["nv1", "nv2", "nv3", "nv4"] # o niveles correspondientes
     with sqlite3.connect(last_sqlite_path) as conn:
         pd.DataFrame({"column": cols}).to_sql("columns_to_review", conn, if_exists="replace", index=False)
     ```
  3. Eliminar las carpetas de anomalía creadas por el error:
     ```bash
     rm -rf /mnt/datos1/data_process/<PAIS>/<ID_PADRE>/<ANIO>/<MES>/*__report_structure_change
     ```
  4. Disparar `C_<PAIS>_<ID>` con el código de subreporte:
     ```bash
     airflow dags trigger C_<PAIS>_<ID> --conf '{"file": "<RUTA_ARCHIVO>", "code": "<CODIGO_SUBREPORTE>", "id_download": 1}'
     ```

---

### Caso B: `Level verification failed` por `"-"` en Niveles Terminales
* **Síntoma:** `verify_levels` falla con:
  ```text
  Extraction error: Column 'nvX' contains values that do not match the expected levels: '-'
  ```
* **Causa:** Cuando una categoría no tiene subdivisión, el código le asigna `"-"` en vez de `None`. La función `isLevel()` normaliza quitando símbolos, produciendo strings vacíos y fallando el fuzzy match (< 90%).
* **Solución:**
  1. Editar el robot en `models/conversion/C_.../<REPORTE>.py`.
  2. Modificar la asignación de término/instrumento:
     ```python
     term = raw_term if raw_term and raw_term not in ("-", "- - -", "nan", "") else None
     ```
  3. Copiar el archivo al worker (`docker cp`) y re-ejecutar la conversión.

---

### Caso C: Error en Migración (`post_load_error`)
* **Síntoma:** La tarea `post_load` bifurca a `notify_post_load_error` porque:
  ```text
  num_records_added != load_metadata['num_records']
  ```
* **Causa:** Registros duplicados en la tabla destino de PostgreSQL (provocados por corridas concurrentes o pre_loads interrumpidos).
* **Solución:**
  1. Verificar duplicados en PostgreSQL:
     ```sql
     SELECT fecha, count(*) FROM "<SCHEMA>"."<TABLE>" GROUP BY fecha ORDER BY fecha DESC;
     ```
  2. Limpiar los registros duplicados en el rango de fechas a migrar:
     ```sql
     DELETE FROM "<SCHEMA>"."<TABLE>" WHERE fecha >= '<MIN_FECHA>' AND fecha <= '<MAX_FECHA>';
     ```
  3. Re-disparar el DAG de migración:
     ```bash
     airflow dags trigger M_<PAIS>_<ID> --conf '{"code": "<CODIGO_SUBREPORTE>", "conversion_path": "<RUTA_SQLITE>", "id_conversion": 1}'
     ```

---

### Caso D: Error `No se encontró reporte en BD para report_code='D_...'`
* **Síntoma:** La tarea `get_conversion_data` falla con `ValueError: No se encontró reporte en BD para report_code=...`.
* **Causa:** Se disparó el DAG pasando el código del archivo (`D_BO_000000XXX`) en lugar del código del subreporte (`D_BO_000000XXX_01`).
* **Solución:**
  Disparar siempre indicando el subreporte registrado en la tabla `report`:
  ```bash
  airflow dags trigger C_<DAG> --conf '{"file": "...", "code": "<REPORTE>_01", "id_download": 1}'
  ```

---

## 📋 3. Cierre en Taiga tras Reparar un DAG

Cuando el DAG pase a `success` y el monitor reporte `SYNCED`:
1. Buscar el User Story asociado al incidente en Taiga (Proyecto 9).
2. Actualizar el estado a **Done** (ID: 54):
   ```python
   import requests
   # PATCH http://10.0.0.16:5000/api/v1/userstories/<ID>
   payload = {'status': 54, 'version': current_version}
   ```
