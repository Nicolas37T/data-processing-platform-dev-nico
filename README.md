# Plataforma de Procesamiento de Datos — DATAX

Pipeline ETL de cuatro etapas basado en **Apache Airflow 3.2.2** para automatizar la recolección, conversión, migración y generación de productos de datos estadísticos.

```
Descarga → Conversión → Migración → Producto
(D_XX_*)   (C_XX_*)    (M_XX_*)   (DB_XX_*)
```

---

## Requisitos previos

| Herramienta | Versión mínima |
|-------------|----------------|
| Docker | 24 |
| Docker Compose | 2.20 |
| Git | cualquiera |

En Linux también necesitas saber tu `UID` de usuario (`id -u`).

---

## Despliegue paso a paso

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd data-processin-platform-template
```

### 2. Crear el archivo de variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y ajusta al menos estas dos variables:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `COUNTRY` | Código ISO de 2 letras del país | `PE`, `BO`, `CL` |
| `AIRFLOW_UID` | UID del usuario Linux (solo Linux) | `1000` |

En **Linux**, obtén tu UID con:

```bash
echo "AIRFLOW_UID=$(id -u)" >> .env
```

En **macOS / Windows con Docker Desktop** no es necesario.

> El valor de `COUNTRY` determina el nombre de las bases de datos del data warehouse:
> `DATA_DB_PE` y `DATA_DB_PE_AUX` para Perú, por ejemplo.

### 3. Crear los directorios necesarios

```bash
mkdir -p logs config data
```

### 4. Construir la imagen Docker

```bash
docker compose build
```

Este paso instala todas las dependencias Python (incluyendo dbt-postgres) sobre la imagen oficial de Airflow. Solo es necesario cuando cambia `requirements.txt` o el `Dockerfile`.

### 5. Inicializar la plataforma (primer arranque)

```bash
docker compose up airflow-init
```

`airflow-init` ejecuta automáticamente, en orden:
1. Verifica recursos mínimos (RAM, CPU, disco).
2. Aplica las migraciones de la base de datos de Airflow.
3. Crea el usuario administrador.
4. Registra las conexiones `platform_db` (PostgreSQL) y `mongo_db` (MongoDB) en Airflow.

Mientras tanto, el contenedor de PostgreSQL ejecuta los scripts de `docker/`:
- Crea la base de datos `platform_db` con toda su estructura de tablas.
- Crea `DATA_DB_{COUNTRY}` (data warehouse vacío).
- Crea `DATA_DB_{COUNTRY}_AUX` (base de reemplazos de texto, vacía).

Espera a que `airflow-init` termine con código de salida `0` antes de continuar.

### 6. Levantar todos los servicios

```bash
docker compose up -d
```

Servicios que se levantan:

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| `postgres` | — | PostgreSQL 16 (Airflow + bases de negocio) |
| `mongo` | — | MongoDB 7 (raw data de conversión) |
| `redis` | 6379 | Broker Celery |
| `airflow-apiserver` | **8080** | UI y API REST de Airflow |
| `airflow-scheduler` | — | Planificador de DAGs |
| `airflow-dag-processor` | — | Procesador de archivos DAG |
| `airflow-worker` | — | Ejecutor Celery |
| `airflow-triggerer` | — | Triggers asíncronos |

Verifica que todos los servicios estén saludables:

```bash
docker compose ps
```

### 7. Acceder a la interfaz de Airflow

Abre en tu navegador: [http://localhost:8080](http://localhost:8080)

- **Usuario:** `airflow` (o el que configuraste en `.env`)
- **Contraseña:** `airflow`

### 8. Generar DAGs del pipeline

El generador de DAGs lee la configuración de `platform_db` y crea los archivos `.py` en `dags/`.

```bash
docker compose exec airflow-worker python include/main-generate.py
```

El script presenta un menú interactivo:

```
Seleccione el proceso a generar:
  1. download
  2. conversion
  3. migration
  4. product

Seleccione los códigos:
  1. Todos
  2. Ingresar códigos manualmente (separados por coma)
```

Los DAGs generados aparecen automáticamente en la UI de Airflow en unos segundos (el dag-processor los detecta).

---

## Estructura de directorios

```
.
├── data/                      # Datos del despliegue (ignorados por git)
│   └── {COUNTRY}/             # Subcarpeta por código de país (ej. BO/, PE/)
│       ├── downloads/         # Archivos descargados de las fuentes
│       └── process/           # Archivos procesados (SQLite, Excel de conversión)
├── dags/
│   ├── download/              # DAGs concretos de descarga (D_XX_*.py)
│   ├── conversion/            # DAGs de conversión (C_XX_*.py)
│   ├── migration/             # DAGs de migración (M_XX_*.py)
│   ├── product/               # DAGs de producto (DB_XX_*.py)
│   ├── templates/             # Templates reutilizables por tipo de DAG
│   └── log_cleaner.py
├── models/
│   ├── download/              # Clases de descarga por fuente
│   ├── conversion/            # Clases de conversión por reporte
│   ├── migration/             # Clases de migración por reporte
│   └── product/               # Clases de producto
├── plugins/
│   └── operators/             # Operadores Airflow custom
├── include/
│   └── main-generate.py       # Generador de DAGs por consola
├── docker/
│   ├── init-db.sh             # Script de inicialización de bases de datos
│   ├── platform_db.sql        # DDL completo de platform_db
│   └── seed_test_{COUNTRY}.sql # (Opcional) Seed de datos de prueba
├── .env.example               # Plantilla de variables de entorno
├── Dockerfile                 # Imagen custom basada en airflow:3.2.2
├── docker-compose.yaml        # Orquestación local con CeleryExecutor
└── requirements.txt           # Dependencias Python
```

> La carpeta `data/{COUNTRY}/` es creada automáticamente por Docker al montar los volúmenes. Los contenidos se persisten en el host — no se pierden al reiniciar los contenedores. El directorio `data/` está en `.gitignore` para que los archivos descargados y procesados no se suban al repositorio.

---

## Bases de datos

| Base de datos | Host interno | Propósito |
|---------------|-------------|-----------|
| `airflow` | `postgres:5432` | Metadata de Airflow |
| `platform_db` | `postgres:5432` | Configuración del pipeline (fuentes, reportes, DAGs) |
| `DATA_DB_{COUNTRY}` | `postgres:5432` | Data warehouse — tablas de migración y producto |
| `DATA_DB_{COUNTRY}_AUX` | `postgres:5432` | Tablas de reemplazos para normalización de texto |
| `airflow` (Mongo) | `mongo:27017` | Raw data antes de migración |

Credenciales internas (entre contenedores):
- PostgreSQL: `postgres` / `datax`
- MongoDB: `airflow` / `airflow`

---

## Rutas internas de datos

Dentro de los contenedores Airflow, los datos se almacenan en:

| Ruta interna | Host (relativa al proyecto) | Propósito |
|---|---|---|
| `/data/downloads/` | `./data/{COUNTRY}/downloads/` | Archivos descargados por el DAG de Descarga |
| `/data/process/` | `./data/{COUNTRY}/process/` | SQLite + Excel generados por el DAG de Conversión |

Usa estas rutas al registrar `file.path` y `report.path` en `platform_db`.

---

## dbt

Los templates `product_dbt_template.py` y `product_star_model_template.py` ejecutan modelos dbt via `BashOperator`. dbt-postgres está instalado en la imagen Docker.

Estructura esperada dentro del contenedor:

```
~/platform_project/dbt/product/
├── dbt_project.yml
├── profiles.yml
└── models/
    └── <id_dag>.sql
```

Para ejecutar dbt manualmente:

```bash
docker compose exec airflow-worker bash -c "cd ~/platform_project/dbt/product && dbt run --select <modelo>"
```

---

## Variables de entorno de referencia

| Variable | Valor por defecto | Descripción |
|----------|------------------|-------------|
| `COUNTRY` | `XX` | Código de país del despliegue |
| `AIRFLOW_UID` | `50000` | UID del usuario Airflow (Linux) |
| `DATA_DB_HOST` | `postgres` | Host del data warehouse |
| `DATA_DB_PORT` | `5432` | Puerto del data warehouse |
| `DATA_DB_USER` | `postgres` | Usuario del data warehouse |
| `DATA_DB_PASSWORD` | `datax` | Contraseña del data warehouse |
| `BUSINESS_DB_HOST` | `postgres` | Host de platform_db |
| `BUSINESS_DB_PORT` | `5432` | Puerto de platform_db |
| `BUSINESS_DB_USER` | `postgres` | Usuario de platform_db |
| `BUSINESS_DB_PASSWORD` | `datax` | Contraseña de platform_db |
| `BUSINESS_DB_DATABASE` | `platform_db` | Nombre de la base de metadatos |
| `AIRFLOW_CONN_PLATFORM_DB` | `postgresql://postgres:datax@postgres:5432/platform_db` | Conexión auto-registrada |

---

## Comandos útiles

```bash
# Ver logs en tiempo real de un servicio
docker compose logs -f airflow-worker

# Ejecutar un DAG manualmente desde la CLI
docker compose exec airflow-apiserver airflow dags trigger D_BO_000000001

# Reiniciar solo el scheduler (sin reconstruir)
docker compose restart airflow-scheduler

# Reconstruir imagen tras cambios en requirements.txt
docker compose build && docker compose up -d

# Detener toda la plataforma (preserva volúmenes)
docker compose down

# Detener y eliminar todos los datos (reinicio completo)
docker compose down -v
```

> **Advertencia:** `docker compose down -v` elimina todos los datos de PostgreSQL y MongoDB. Úsalo solo si quieres reiniciar desde cero.
