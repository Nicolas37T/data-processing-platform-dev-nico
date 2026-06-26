# Data Processing Platform — DATAX

## Qué hace este proyecto

Plataforma de procesamiento de datos basada en **Apache Airflow** que automatiza un pipeline ETL de cuatro etapas para la recolección, conversión y carga de datos estadísticos (principalmente de fuentes gubernamentales de Perú/Bolivia).

### Pipeline principal

```
Download → Conversion → Migration → Product
(D_XX_*)    (C_XX_*)    (M_XX_*)   (DB_XX_*)
```

Cada etapa es un DAG de Airflow que al terminar exitosamente dispara automáticamente el DAG de la siguiente etapa via `TriggerDagRunOperator`.

**1. Download** (`dags/templates/file_download_template.py`)
- Verifica que la URL de la fuente esté accesible
- Descarga archivos (xlsx, pdf, csv, xml, xls)
- Compara con la descarga anterior para detectar actualizaciones
- Registra en PostgreSQL y dispara DAGs de Conversion

**2. Conversion** (`dags/templates/conversion_template.py`)
- Lee y valida la integridad del archivo descargado
- Extrae datos estructurados del documento
- Normaliza texto con fuzzy matching (`rapidfuzz`) y tabla de reemplazos en PostgreSQL
- Valida estructura contra conversión anterior
- Guarda resultado en SQLite + Excel, inserta raw data en MongoDB
- Dispara DAGs de Migration

**3. Migration** (`dags/templates/migration_template.py`)
- Carga datos convertidos a tablas PostgreSQL de almacenamiento (`DATA_DB_{country_code}`)
- Hace backup previo y restore automático si el load falla
- Valida que el número de registros insertados sea correcto
- Dispara DAGs de Product

**4. Product** (`dags/templates/product_template.py`, `product_dbt_template.py`, `product_star_model_template.py`)
- Genera tablas de producto / modelos estrella / transformaciones dbt

### Convención de nombres de DAGs

| Prefijo | Etapa | Ejemplo |
|---------|-------|---------|
| `D_PE_` | Download (Perú) | `D_PE_000000001` |
| `C_PE_` | Conversion (Perú) | `C_PE_000000001_1` |
| `M_PE_` | Migration (Perú) | `M_PE_000000001` |
| `DB_PE_` | Product / Database | `DB_PE_ejemplo` |

Los DAGs concretos viven en `dags/download/` y sus modelos en `models/download/`, `models/conversion/`, `models/migration/`.

### Clases base

| Clase | Archivo | Función |
|-------|---------|---------|
| `Download_Base` | `models/download/Download_Base.py` | Verificación de URL, descarga de archivos, almacenamiento por frecuencia de publicación |
| `Conversion_Base` | `models/conversion/Conversion_Base.py` | Lectura/validación de archivos, normalización de texto, validación de estructura, guardado SQLite/Excel |
| `Migration_Base` | `models/migration/Migration_Base.py` | Pre-load/post-load con backup, carga a PostgreSQL, validación de registros |
| `Product_Base` | `models/product/Product_Base.py` | Base para DAGs de producto |

### Operadores custom (`plugins/operators/`)

- `SelectPostgresOperator`: SELECT con parámetros retornando resultados via XCom
- `MongoCustomOperator` / `MongoFileInsertOperator`: inserción en MongoDB
- `ConversionStatusLog`: registro de estado de conversión
- `CustomTaskInfoOperator`: info de tareas

### Frecuencias de publicación soportadas

`diario`, `semanal`, `mensual`, `trimestral`, `semestral`, `anual`

La función `createDirectoryStruct` organiza los archivos en carpetas por año/mes/día según la frecuencia.

---

## Versiones

### Infraestructura (Docker)

| Componente | Versión |
|-----------|---------|
| Apache Airflow | **2.10.4** |
| PostgreSQL | **13** |
| Redis | **7.2-bookworm** |
| Java (JRE) | **OpenJDK 11** (requerido por tabula-py) |

### Python — Librerías principales

| Librería | Versión | Uso |
|---------|---------|-----|
| `pandas` | `>=2.1.2,<2.2` | Procesamiento de datos |
| `numpy` | flexible | Operaciones numéricas |
| `pyarrow` | flexible | Serialización columnar |
| `openpyxl` | flexible | Lectura/escritura xlsx |
| `xlrd` | flexible | Lectura xls legacy |
| `xlwings` | flexible | Automatización Excel |
| `PyMuPDF` (fitz) | flexible | Extracción de PDFs |
| `pdfplumber` | flexible | Extracción tablas PDF |
| `tabula-py` | flexible | Extracción tablas PDF (requiere Java) |
| `pypdf` | flexible | Manipulación PDF |
| `playwright` | flexible | Web scraping / automatización |
| `beautifulsoup4` | flexible | Parsing HTML |
| `rapidfuzz` | flexible | Fuzzy matching para normalización de texto |
| `unidecode` | flexible | Normalización Unicode |
| `cohere` | flexible | LLM / IA para extracción |
| `huggingface-hub` | flexible | Modelos de ML |
| `gdown` | flexible | Descarga desde Google Drive |
| `looker-sdk` | flexible | Integración con Looker |
| `rich` | flexible | Output en consola |

### Airflow Providers

| Provider | Uso |
|---------|-----|
| `apache-airflow-providers-postgres` | BD de plataforma y almacenamiento |
| `apache-airflow-providers-mongo` | Almacenamiento raw data |
| `apache-airflow-providers-amazon` | AWS S3 |
| `apache-airflow-providers-google` | GCS, BigQuery |
| `apache-airflow-providers-microsoft-azure` | Azure Blob, Data Lake, Key Vault |
| `apache-airflow-providers-snowflake` | Data warehouse |
| `apache-airflow-providers-slack` | Notificaciones |
| `apache-airflow-providers-redis` | Celery broker |
| `apache-airflow-providers-sendgrid` | Email |
| `apache-airflow-providers-elasticsearch` | Búsqueda/logs |

### Cloud SDKs

| SDK | Uso |
|-----|-----|
| `azure-storage-blob` | Azure Blob Storage |
| `azure-storage-file-datalake` | Azure Data Lake |
| `azure-keyvault-secrets` | Secretos en Azure |
| `azure-identity` | Autenticación Azure |
| `google-cloud-storage` | GCS |
| `google-cloud-bigquery` | BigQuery |
| `google-cloud-secret-manager` | Secretos GCP |
| `snowflake-connector-python` | Snowflake |

---

## Arquitectura Docker

El `docker-compose.yaml` levanta:

- `airflow-webserver` → UI en puerto 8080
- `airflow-scheduler` → planificador de DAGs
- `airflow-worker` → ejecutor Celery (puede escalar horizontalmente)
- `airflow-triggerer` → manejo de triggers asíncronos
- `postgres:13` → metadata de Airflow
- `redis:7.2` → broker Celery

**Ejecutor:** `CeleryExecutor`  
**Zona horaria:** `America/La_Paz` (Bolivia)

---

## Bases de datos

| BD | Uso |
|----|-----|
| `airflow` (PostgreSQL) | Metadata de Airflow, logs de ejecución, excepciones |
| `DATA_DB_{country_code}` (PostgreSQL en `10.0.0.12:5432`) | Almacenamiento de datos convertidos por país |
| `DATA_DB_{country_code}_AUX` (PostgreSQL) | Tablas de reemplazos de texto |
| MongoDB (`mongo_db`) | Almacenamiento raw data antes de migración |

---

## Estructura de directorios

```
.
├── dags/
│   ├── download/          # DAGs concretos de descarga (D_PE_XXXXXXXXX.py)
│   ├── templates/         # Templates reutilizables por tipo de DAG
│   └── log_cleaner.py     # Limpieza de logs
├── models/
│   ├── download/          # Clases de descarga por fuente
│   ├── conversion/        # Clases de conversión por reporte
│   ├── migration/         # Clases de migración por reporte
│   └── product/           # Clases de producto
├── plugins/
│   └── operators/         # Operadores Airflow custom
├── include/               # Utilidades y generadores de DAGs
├── Dockerfile             # Imagen custom basada en apache/airflow:2.10.4
├── docker-compose.yaml    # Orquestación local con CeleryExecutor
└── requirements.txt       # Dependencias Python
```

---

## Comandos útiles

```bash
# Levantar la plataforma
docker-compose up -d

# Construir imagen con cambios en requirements.txt
docker-compose build && docker-compose up -d

# Ver logs de un worker
docker-compose logs -f airflow-worker

# Acceder a la UI de Airflow
open http://localhost:8080  # user: airflow / pass: airflow

# Ejecutar un DAG manualmente
docker-compose exec airflow-webserver airflow dags trigger D_PE_000000001
```
