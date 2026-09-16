# 📖 Manual Definitivo: Creación e Implementación de un DAG de Conversión (Plataforma V2)

Este manual documenta el **flujo de trabajo completo de 13 pasos**, actualizado con los estándares de la **Plataforma V2** (Airflow 3, PostgreSQL 17, servidor `10.0.0.16`), incluyendo todas las correcciones críticas y lecciones aprendidas durante la implementación.

---

## **Paso 1: Crear la incidencia en Jira**

Crea una nueva incidencia (ticket) del tipo **`conversion request flow`** completando los campos obligatorios:

- **Nombre del soporte:** Nombre descriptivo del reporte (ej. *Fondos de Inversión Cartera Participantes y Tasas de Rendimiento*).
- **Número de página:** Entero $\ge 1$ donde inicia la tabla a extraer en el documento.
- **Frecuencia de publicación:** Diario, semanal, mensual, etc.
- **Separador decimal:** `.` (punto) o `,` (coma).
- **Factor de conversión:** Magnitud reportada (generalmente vacío o `1`).
- **Código de conversión (`conversion code`):** Debe coincidir con el código de descarga asociado (ej. `D_BO_000000481_01`).
- **Imágenes de referencia:** Capturas del PDF original y de la estructura tabulada esperada.

---

## **Paso 2: Mover la incidencia a "En curso"**

Al cambiar el estado del ticket a **"En curso"** (*In Progress*), la automatización de Jira:
1. Crea automáticamente la rama en Git (ej. `cristhian/D_BO_000000481_01`).
2. Registra la fila del reporte en la tabla `report` de la base de datos `platform_db`.
3. Pre-crea la estructura base de carpetas en `models/conversion/`.

---

## **Paso 3: Obtener la rama localmente**

En tu terminal local de desarrollo:

```bash
git fetch origin
git checkout cristhian/D_BO_000000481_01
git pull origin cristhian/D_BO_000000481_01
```

Verás creada la carpeta del robot en:
`models/conversion/C_BO_000000481/D_BO_000000481_01.py`

---

## **Paso 4: Integrar y estandarizar el código del freelancer**

Pega el código del freelancer en `models/conversion/C_BO_000000481/D_BO_000000481_01.py` aplicando los siguientes estándares:

### Reglas de estandarización:
1. **Nombre de la clase:** Debe llamarse exactamente igual al ID del archivo:
   ```python
   class D_BO_000000481_01(Conversion_Base):
   ```
2. **Herencia e Imports:**
   ```python
   import os
   import re
   import traceback
   from datetime import datetime
   import pandas as pd
   import pdfplumber

   from models.conversion.Conversion_Base import Conversion_Base
   from models.conversion.tools.conversion_tools import (
       get_col_date,
       get_pdf_report_page,
       search_key_words,
       to_numeric_datax,
   )
   ```
3. **Manejo de errores:** Agregar `traceback.print_exc()` en los bloques `except`:
   ```python
   except Exception as error:
       print(f"Could not extract report from {file_path}: {error}")
       traceback.print_exc()
       return ""
   ```
4. **Limpieza e Imports Absolutos:** 
   - Eliminar `sys.path.append("..")` o rutas relativas manuales.
   - ⚠️ **Nunca usar** `from conversion_tools import ...`. Siempre importar desde el paquete completo: `from models.conversion.tools.conversion_tools import ...`.
5. **Archivo `__init__.py` obligatorio:**
   Crea siempre un `__init__.py` vacío en `models/conversion/C_.../` para que Airflow y unittest puedan cargar dinámicamente el módulo sin arrojar `ModuleNotFoundError`.
6. **Estructura de Niveles (`nv1` hasta `nv5`):**
   - El robot soporta de `nv1` hasta `nv5` según la granularidad jerárquica del reporte.
   - Las columnas finales del DataFrame deben terminar en `fecha` y `valor`:
     `[..., 'nv1', 'nv2', ..., 'fecha', 'valor']`.

---

## **Paso 5: Configurar la base de datos del negocio (`platform_db` ➔ tabla `report`)**

Conéctate a la base de datos `platform_db` (en `10.0.0.16:5434`) y ajusta el registro del reporte:

```sql
UPDATE report 
SET 
    is_active = true,
    storage_table = 'BBV;DATA_D_BO_000000481_01',
    replacement_table = 'bbv;repl_D_BO_000000481_01',
    key_words = 'cartera participantes tasas rendimiento',
    path = '\\\\10.0.0.16\\data_process\\BO\\D_BO_000000481\\',
    page_number = 2,
    decimal_separator = '.',
    file_extension = 'sqlite'
WHERE code = 'D_BO_000000481_01';
```

### ⚠️ Puntos críticos aprendidos:
- **`storage_table`:** Debe tener el formato `ESQUEMA;TABLA` (ej. `BBV;DATA_D_BO_000000481_01`). **Nunca poner rutas de archivos Excel**.
- **`path`:** Usar la ruta Windows estándar terminando en barra invertida `\\10.0.0.16\data_process\BO\D_BO_000000481\`.

---

## **Paso 6: Configurar y ejecutar el test unitario**

Edita `models/conversion/tests/test_conversion.py`:

```python
REPORT_CODE = 'D_BO_000000481_01'
FILE_PATH = "models/conversion/C_BO_000000481/2026-08-17_Resumen.pdf"
```

### 1. Comentar la llamada a `text_match`:
```python
#* comentar para pruebas intermedias        
# replaces_dict, report_df = self.robot.text_match(...)
#*        
```

### 2. Exportar el SQLite con el nombre exacto de la tabla:
En el test, guarda el SQLite en la carpeta del modelo, **nombrando la tabla interna exactamente igual al código del reporte**:

```python
# Guardar en SQLite dentro de models para que se sincronice
output_sqlite = f"models/conversion/C_BO_000000481/{REPORT_CODE}.sqlite"
sqlite_engine = create_engine(f"sqlite:///{output_sqlite}")
final_df.to_sql(REPORT_CODE, con=sqlite_engine, if_exists="replace", index=False)
```

### 3. Ejecutar la prueba dentro del contenedor:
```bash
docker exec -it data-processing-platform-dev-airflow-worker-1 python -m unittest models/conversion/tests/test_conversion.py
```
> Debe terminar en **`OK`**.

---

## **Paso 7: Ejecutar test de reemplazos y realizar limpieza**

1. **Descomentar** la línea de `text_match` en `test_conversion.py`:
   ```python
   replaces_dict, report_df = self.robot.text_match(df=report_df, db_aux_conn=self.engine, replacement_table_name=self.replacement_table[1], replacement_table_schema=self.replacement_table[0], table_exists=self.table_exists, first_execution=True, dag_run_date=datetime.now())
   ```
2. **Ejecutar el test** nuevamente:
   ```bash
   docker exec -it data-processing-platform-dev-airflow-worker-1 python -m unittest models/conversion/tests/test_conversion.py
   ```
   Esto creará automáticamente la tabla `bbv.repl_D_BO_000000481_01` en `DATA_DB_BO_AUX`.
3. **Mantenimiento inicial:** Abre tu cliente SQL (DBeaver), entra a `DATA_DB_BO_AUX` ➔ tabla `repl_D_BO_000000481_01` y normaliza textos (capitalización, siglas, etc.).

---

## **Paso 8: Configurar "columns_to_review" en el archivo SQLite**

Dentro del archivo `D_BO_000000481_01.sqlite` generado en `models/conversion/C_BO_000000481/`:

### ⚠️ Reglas críticas para la V2:
- La tabla debe llamarse **`columns_to_review`** *(en minúsculas, con `n` y `_`)*.
- La columna debe llamarse **`column`** *(en inglés)*.
- **SOLO incluir niveles y categorías** (todas las columnas de niveles presentes en el reporte, ej. `fecha`, `nv1`, `nv2`, `nv3`, `nv4`, `nv5`, `nv6`, `nv7`, `nv8`).
- 🚫 **NUNCA incluir `valor` ni metadatos (`file`, `tituloX`)**: Los montos numéricos cambian todos los días y dispararían una falsa alarma de cambio de estructura.

### Comando directo para crearla e inicializarla (compatible con Windows PowerShell y Linux):
```bash
python -c "import sqlite3; conn = sqlite3.connect('models/conversion/C_BO_000000481/D_BO_000000481_01.sqlite'); cur = conn.cursor(); cur.execute('DROP TABLE IF EXISTS columns_to_review'); cur.execute('CREATE TABLE columns_to_review (column TEXT)'); cur.executemany('INSERT INTO columns_to_review (column) VALUES (?)', [('fecha',), ('nv1',), ('nv2',), ('nv3',), ('nv4',), ('nv5',), ('nv6',), ('nv7',), ('nv8',)]); conn.commit(); cur.execute('SELECT name FROM sqlite_master WHERE type=?', ('table',)); print('✅ Tablas listas:', [t[0] for t in cur.fetchall()]); conn.close()"
```
*(Las tablas resultantes dentro del SQLite deben ser: `['D_BO_000000481_01', 'columns_to_review']`)*.

---

## **Paso 9: Subir la plantilla SQLite de referencia y registrarla en BD**

Para que Airflow pueda validar la estructura en futuras ejecuciones y en la primera corrida:

### 1. Copiar el SQLite de referencia a la carpeta del servidor
Sube el archivo `models/conversion/C_BO_000000481/D_BO_000000481_01.sqlite` a la carpeta base del reporte en el servidor:
`/mnt/datos1/data_process/BO/D_BO_000000481/D_BO_000000481_01.sqlite`

### 2. Registrar la ruta en la tabla `report` de `platform_db`
Usa la ruta en formato Windows estándar (la plataforma la traduce internamente con `convert_win_path()`):

```sql
UPDATE report 
SET converted_report_path = '\\\\10.0.0.16\\data_process\\BO\\D_BO_000000481\\D_BO_000000481_01.sqlite'
WHERE code = 'D_BO_000000481_01';
```

> 💡 **Nota sobre la 1ª ejecución:** Si es un reporte totalmente nuevo y no deseas validar contra ninguna plantilla previa en la primera corrida, puedes configurar temporalmente `converted_report_path = NULL`.

---

## **Paso 10: Generar el DAG en el proyecto**

En la Plataforma V2, usa el generador unificado por consola:

```bash
docker exec -it data-processing-platform-dev-airflow-worker-1 python include/main-generate.py
```

1. Selecciona la opción **`2. Conversion`**.
2. Selecciona **`1. Enter robot code(s)`**.
3. Ingresa el código padre: **`C_BO_000000481`**.
4. Se generará automáticamente el wrapper en `dags/conversion/C_BO_000000481.py`.

---

## **Paso 11: Infraestructura Docker, permisos y Push al servidor**

### 1. Verificar volúmenes en `docker-compose.yaml`
Asegúrate de que `docker-compose.yaml` monte las carpetas de datos en los servicios de Airflow:
```yaml
  volumes:
    - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
    - ${AIRFLOW_PROJ_DIR:-.}/models:/opt/airflow/models
    - /mnt/datos1/downloaded_files:/mnt/datos1/downloaded_files
    - /mnt/datos1/data_process:/mnt/datos1/data_process
```

### 2. Permisos de escritura en el servidor
En el host del servidor, otorga permisos totales:
```bash
sudo chmod -R 777 /mnt/datos1/data_process
```

### 3. Commit y Push de los cambios
```bash
git add models/conversion/C_BO_000000481/ dags/conversion/C_BO_000000481.py
git commit -m "feat(conversion): implement and configure robot C_BO_000000481_01"
git push origin cristhian/D_BO_000000481_01
```

---

## **Paso 12: Probar el DAG en Airflow a través de CLI / API**

Como los DAGs de conversión no tienen ejecución aislada (requieren el archivo de descarga descargado previamente por su DAG de descarga correspondiente), para probarlos manualmente:

### Comando de disparo en Linux / Bash (usar comillas simples para el `--conf`):
```bash
docker exec data-processing-platform-dev-airflow-worker-1 airflow dags trigger C_BO_000000481 --conf '{"code": "D_BO_000000481_01", "id_download": 28857, "file": "\\\\10.0.0.16\\spim\\BO\\D_BO_000000481\\2026\\2026-08\\2026-08-27_boletin diario.pdf"}'
```

### 💡 Diagnóstico y Solución de Problemas Comunes:

1. **`FileNotFoundError` en `read_file` (Estructura de Carpetas según Frecuencia):**
   La ruta del archivo descargado varía según la frecuencia configurada en el robot de descarga:
   - **Frecuencia Mensual / Estándar:** Los archivos se guardan directamente bajo el mes:
     `\\10.0.0.16\spim\BO\D_BO_XXXXX\YYYY\YYYY-MM\YYYY-MM-DD_nombre.ext`
     *(En Linux: `/mnt/datos1/downloaded_files/BO/D_BO_XXXXX/YYYY/YYYY-MM/`)*
   - **Frecuencia Diaria con Subcarpeta por Día:** Algunos robots crean una carpeta adicional para el día exacto:
     `\\10.0.0.16\spim\BO\D_BO_XXXXX\YYYY\YYYY-MM\YYYY-MM-DD\YYYY-MM-DD_nombre.ext`
     *(En Linux: `/mnt/datos1/downloaded_files/BO/D_BO_XXXXX/YYYY/YYYY-MM/YYYY-MM-DD/`)*

   > ⚠️ **Antes de disparar el trigger manual:** Siempre inspecciona primero la carpeta en el servidor con:
   > ```bash
   > ls -la /mnt/datos1/downloaded_files/BO/<CODIGO_DESCARGA>/YYYY/YYYY-MM/
   > ```
   > Si ves una subcarpeta con la fecha (ej. `2026-08-31/`), la ruta en el `--conf` debe incluir esa subcarpeta. Si los archivos están directamente en `2026-09/`, la ruta va directo con `\YYYY\YYYY-MM\archivo.ext`.
   Ajusta el parámetro `"file"` con el nombre real del archivo.

2. **El DAG termina en `no_updates`:**
   Si la fecha del reporte a procesar es $\le$ a `converted_to` en la base de datos, resetea la fecha para forzar la re-conversión:
   ```sql
   UPDATE report SET converted_to = '2026-08-01' WHERE code = 'D_BO_000000481_01';
   ```

3. **Salta a `notify_structure_change` en vez de guardar el reporte:**
   Ocurre cuando las columnas del reporte nuevo no coinciden con las de la plantilla previa configurada en `converted_report_path` (ej. nombres antiguos de columnas o niveles diferentes).
   - **Solución:** Reemplazar el `.sqlite` de referencia en `/mnt/datos1/data_process/BO/D_BO_000000481/D_BO_000000481_01.sqlite` con el nuevo generado en el **Paso 8**, o fijar `converted_report_path = NULL` para la primera corrida.

4. **`IndexError: list index out of range` en `_get_conversion_data`:**
   Ocurre si al disparar el trigger manual se olvida pasar `"code"` en el diccionario `--conf`. La tarea `_get_conversion_data` ejecuta `SELECT ... WHERE r.code = %s` esperando el código del reporte (`D_BO_..._01`). Si falta, busca `NULL`, la consulta retorna 0 filas y `results[0]` arroja `IndexError`.
   - **Solución:** Incluir siempre `"code": "<CODIGO_REPORTE>"` en el payload:
     ```bash
     --conf '{"code": "D_BO_000000270_01", "id_download": 1, "file": "..."}'
     ```

5. **`converted_to` (o `migrated_to`) permanece vacío (`NULL`) tras una ejecución exitosa:**
   Ocurre si en `dags/conversion/sql/update_report.sql` la condición es `'fecha' > converted_to`. En PostgreSQL, `'fecha' > NULL` evalúa a `NULL` (falsy), afectando 0 filas.
   - **Solución:** Asegurar que `update_report.sql` contenga la condición agrupada:
     ```sql
     AND ('{{ ti.xcom_pull(task_ids='report_data_validation', key='converted_file')['converted_to'] }}' > converted_to OR converted_to IS NULL);
     ```

### Resultado esperado:
- Todas las tareas principales en **Verde Oscuro (Success)**:
  `get_conversion_data` ➔ `read_file` ➔ `extraction` ➔ `structure_review` ➔ `report_data_validation` ➔ `record_conversion` ➔ `update_report` ➔ `trigger_dags`.
- Archivo generado físicamente en el servidor:
  `/mnt/datos1/data_process/BO/D_BO_000000481/2026/2026-08/2026-08-27_D_BO_000000481_01.sqlite`

---

## **Paso 13: Unir cambios a la rama principal (Merge)**

1. Crea el **Pull Request / Merge Request** desde tu rama `cristhian/D_BO_000000481_01` hacia `main`.
2. Verifica que pase el pipeline de CI/CD.
3. Realiza el **Merge**.
4. Cambia el estado de la incidencia en Jira a **"Finalizado" / "Done"**.

---

¡Con esta guía tienes todo el procedimiento blindado de principio a fin! 🚀