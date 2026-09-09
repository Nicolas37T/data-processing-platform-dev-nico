# 📋 Bitácora de Diagnóstico y Resolución de DAGs (BCB / CNDC)

Este documento resume todo el trabajo, análisis, causas raíz y soluciones implementadas durante la sesión de depuración para los DAGs de descarga y conversión de la plataforma de datos.

---

## 1. 🔄 DAG `C_BO_000000418` / `D_BO_000000418_01` (Tasas Interbancarias - BCB)

### Problema Inicial
- El DAG fallaba en la tarea `notify_structure_change` con error de sintaxis SQL:
  `invalid input syntax for type bigint: "None"` al intentar insertar `id_download: 'None'`.
- En `extraction` y `structure_review`:
  - `TypeError: sequence item 0: expected str instance, float found` en `row_text = " ".join(row_values)`.
  - Fallo en `verify_values`: `Value verification failed: 'valor' column contains non-numeric or invalid values: 1 <NA>`.

### Causa Raíz
1. Al unir celdas vacías con `join`, los `NaN` eran flotantes y rompían la cadena.
2. La conversión a `pd.NA` (`.replace({np.nan: pd.NA})`) generaba cadenas `<NA>` no numéricas que hacían fallar `verify_values`.
3. En la plantilla SQL de inserción, si `id_download` venía vacío o `None`, se interpolaba como el texto literal `'None'` en lugar de `NULL`.
4. El paquete `models/conversion/C_BO_000000418` no tenía `__init__.py` y faltaba el archivo DAG local `dags/conversion/C_BO_000000418.py`.

### Solución Implementada
- **`models/conversion/C_BO_000000418/D_BO_000000418_01.py`**:
  - Limpieza de valores nulos antes del join: `row.dropna().astype(str)`.
  - Eliminación del reemplazo por `pd.NA` en la columna `valor`.
  - Limpieza numérica consistente con `to_numeric_datax`.
- **`dags/conversion/sql/insert_conversion.sql`** y **`insert_conversion_status.sql`**:
  - Manejo seguro de `id_download`: `{% if id_download and id_download != 'None' %}'{{ id_download }}'{% else %}NULL{% endif %}`.
- **Creación de archivos**:
  - `models/conversion/C_BO_000000418/__init__.py`.
  - `dags/conversion/C_BO_000000418.py`.

---

## 2. 🔄 DAG `C_BO_000000573` / `D_BO_000000573_01` (Inyecciones y Retiros STI - CNDC)

### Problema Inicial
- El robot de conversión funcionaba correctamente y generaba los archivos SQLite al día en el almacenamiento, pero en la tabla `report` de la base de datos el campo `converted_to` permanecía en blanco / NULL.

### Causa Raíz
- En `dags/conversion/sql/update_report.sql` y `dags/migration/sql/update_report.sql`, la cláusula de actualización era:
  ```sql
  WHERE id_report = '...' AND ('...' > converted_to);
  ```
- En PostgreSQL, cualquier comparación de mayor/menor con un valor `NULL` (`'2026-08-21' > NULL`) evalúa a `NULL` (falso), por lo que el `UPDATE` afectaba 0 filas y `converted_to` nunca se actualizaba si inicialmente estaba vacío.

### Solución Implementada
- Se modificó la condición en `dags/conversion/sql/update_report.sql` y `dags/migration/sql/update_report.sql`:
  ```sql
  AND ('{{ ti.xcom_pull(task_ids='report_data_validation', key='converted_file')['converted_to'] }}' > converted_to OR converted_to IS NULL);
  ```
- Se regularizó el registro `id_report = 396` en `platform_db`.

---

## 3. 🔄 DAG `C_BO_000000568` / `D_BO_000000568_01` (Tipos de Cambio Dólar Pactados con Clientes - BCB)

### Problema Inicial
- `D_BO_000000568_02` estaba al día (`2026-09-02`), pero `D_BO_000000568_01` tenía un rezago de 20 días (`2026-08-13`).
- Errores reportados:
  1. `No module named 'models.conversion.C_BO_000000568.D_BO_000000568_01'`.
  2. `There might be a change in structure: Extraction error: Column 'nv1' contains values that do not match the expected levels: Pío X, Catedral de Potosí, Asunción...`.

### Causa Raíz
1. **Falta de `__init__.py`**: No existía en `models/conversion/C_BO_000000568`, fallando la importación dinámica en Airflow.
2. **Error en lectura Excel**: `get_xlsx_report_dataframe` ejecutaba `search_key_words` con `unidecode` sobre celdas `NaN` tratadas como `float`, provocando `AttributeError: 'float' object has no attribute 'encode'` y abortando la extracción.
3. **Desplazamiento de columnas en el Excel entre agosto y septiembre**:
   - En agosto (`2026-08-13`), la cabecera `"Entidad"` estaba en la columna 2.
   - En septiembre (`2026-09-02`), la columna 0 desapareció y `"Entidad"` se movió a la columna 1.
4. **Falso positivo de estructura en `nv1`**:
   - `nv1` son las entidades financieras (bancos y cooperativas). Las cooperativas sólo aparecen en el reporte los días que transan con clientes.
   - El archivo SQLite del 13 de agosto en el servidor tenía erróneamente `nv1` en la tabla `columns_to_review`. Cuando el 2 de septiembre aparecieron cooperativas que no operaron el 13 de agosto, `verify_levels` lanzó error de estructura.

### Solución Implementada
- **`models/conversion/C_BO_000000568/D_BO_000000568_01.py`**:
  - Lectura segura directa del libro Excel evitando la excepción de `unidecode`.
  - Detección dinámica de `entity_col_idx` previa al forward-fill para soportar variaciones de columnas.
  - Estandarización de mayúsculas en `nv2`: `'Operaciones con Clientes'` y `'Operaciones entre Entidades Financieras'`.
  - Sobrescritura de `structure_review` para excluir explícitamente `nv1` de la verificación de niveles fijos.
  - Sobrescritura de `report_data_validation` para limpiar `nv1` de `columns_to_review` en los nuevos SQLite generados.
- **Creación de archivos**:
  - `models/conversion/C_BO_000000568/__init__.py`.
  - `dags/conversion/C_BO_000000568.py`.

---

## 4. 🔍 Análisis `D_BO_000000487` / `C_BO_000000487` (Tasas de Referencia TRE - BCB)

### Problema Reportado
- El monitor mostraba una alerta de **Desfase Máximo (Lag) de 29 días**:
  - `Fecha última descarga`: `2026-09-30`
  - `converted_to`: `2026-09-01`
  - Excepción histórica: `[Errno 2] No such file or directory: '.../NUEVA TRE GESTION-2026.xlsx'` marcada como `[Superada / Resuelta]`.

### Diagnóstico del Análisis
- **El reporte SÍ está al día y la conversión funcionó correctamente.**
- El archivo del BCB publica las tasas de septiembre con el rango:
  - `Vigencia DESDE`: `2026-09-01`
  - `Vigencia HASTA`: `2026-09-30`
- **Discrepancia entre robots**:
  - El robot de descarga (`D_BO_000000487.py`) tomó la última columna (`Vigencia HASTA` = `2026-09-30`) y nombró el archivo `2026-09-30_tasa referencia.xlsx`.
  - El robot de conversión (`D_BO_000000487_01.py`) tomó `Vigencia DESDE` = `2026-09-01` para ser fiel al histórico de la serie mensual (`2026-06-01`, `2026-07-01`, `2026-08-01`, `2026-09-01`).
- El monitor de Airflow resta `2026-09-30` menos `2026-09-01` y reporta un lag de 29 días, cuando en realidad ambos se refieren al mismo mes (septiembre 2026).

---

## 5. 📂 Ubicación de Registros Crudos del Asistente

Si se requiere auditar el log completo de ejecuciones y comandos de esta sesión, los registros en formato JSONL se encuentran en:
- `C:\Users\DATAX\.gemini\antigravity-ide\brain\e91cd2ad-a5fa-45a2-9f9e-446917bcfa93\.system_generated\logs\transcript.jsonl`
- `C:\Users\DATAX\.gemini\antigravity-ide\brain\e91cd2ad-a5fa-45a2-9f9e-446917bcfa93\.system_generated\logs\transcript_full.jsonl`
