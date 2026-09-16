---
name: crear-robot-migracion
description: Guía completa para crear, probar y desplegar un robot y DAG de migración (PostgreSQL) siguiendo los estándares oficiales de DATAX Platform.
---

# 🚚 Skill: Crear Robot y DAG de Migración

Esta skill guía el desarrollo, prueba, generación y ejecución de robots de migración (`models/migration/M_.../`) que leen los archivos `.sqlite` generados por Conversión y cargan los datos procesados en la base de datos PostgreSQL analítica (`DATA_DB_<PAIS>`) actualizando la auditoría en `platform_db`.

---

## 🏛️ Estructura del Módulo de Migración

Para un reporte con código base `D_PAIS_000000XXX_YY` (ej. `D_BO_000000270_01`):
```text
models/migration/
└── M_BO_000000270/
    ├── D_BO_000000270_01.py    # Lógica de estandarización, métricas y factor
    └── D_BO_000000270_01.sql   # DDL de la tabla y trigger en PostgreSQL
```

---

## 📋 Flujo de Trabajo en 6 Pasos

### Paso 1: Inspeccionar la Estructura de Conversión (`.sqlite`)
1. Abrir o inspeccionar el archivo SQLite generado por la etapa de Conversión:
   ```bash
   sqlite3 /ruta/al/archivo.sqlite ".schema"
   sqlite3 /ruta/al/archivo.sqlite "SELECT * FROM D_BO_000000270_01 LIMIT 5;"
   ```
2. Identificar:
   - Títulos presentes (`titulo1`, `titulo2`, etc.).
   - Niveles jerárquicos presentes (`nv1` hasta `nvN`).
   - Naturaleza del valor (`valor`): ¿En qué unidad viene en la fuente? (ej. millones de BOB, porcentajes, etc.).
   - Métrica correspondiente (`'moneda'`, `'tasa'`, `'indice'`, etc.) y unidad métrica (`'BOB'`, `'USD'`, `'%'`).

### Paso 2: Crear el Archivo SQL DDL (`D_..._XX.sql`)
> [!IMPORTANT]
> **REGLAS ESTRICTAS DE POSTGRESQL**:
> - La plantilla `migration_template.py` espera **exactamente 4 marcadores `%s`**:
>   `% (schema, table, schema, table)` para la tabla y el trigger.
> - Usar `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` (nativo en Postgres).
> - Columnas de auditoría obligatorias: `fecha_creacion date DEFAULT CURRENT_DATE`, `fecha_modificacion timestamp DEFAULT CURRENT_TIMESTAMP`, `observations text`.
> - Columnas de métricas: `metrica character varying(255)`, `unidad_metrica character varying(255)`.
> - **PROHIBIDO** incluir `WITH (OIDS=FALSE)` (removido en Postgres 12+).
> - Usar `CREATE OR REPLACE TRIGGER` (Postgres 14+).

```sql
CREATE TABLE IF NOT EXISTS "%s"."%s"
(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  titulo1 text,
  nv1 text,
  nv2 text,
  nv3 text,
  nv4 text,
  nv5 text,
  fecha date,
  metrica character varying(255),
  unidad_metrica character varying(255),
  valor numeric,
  fecha_creacion date DEFAULT CURRENT_DATE,
  fecha_modificacion timestamp DEFAULT CURRENT_TIMESTAMP,
  observations text
);

CREATE OR REPLACE FUNCTION actualizar_fecha_modificacion()
RETURNS TRIGGER AS $$
BEGIN
  NEW.fecha_modificacion = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trigger_actualizar_fecha_modificacion
BEFORE UPDATE ON "%s"."%s"
FOR EACH ROW
EXECUTE FUNCTION actualizar_fecha_modificacion();
```

### Paso 3: Implementar la Lógica en Python (`D_..._XX.py`)
1. Heredar obligatoriamente de `Migration_Base`.
2. El nombre de la clase debe coincidir exactamente con el código del reporte (ej. `class D_BO_000000270_01(Migration_Base):`).
3. Implementar el método `standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]`:
   - Estandarizar columnas si es necesario.
   - Insertar `metrica` y `unidad_metrica` **ANTES de `valor`**, de modo que `valor` permanezca siempre como la **última columna** (`df.columns[-1]`) para que `process_numeric_column` funcione correctamente.
   - Retornar `(df_dict, df)` donde `df_dict` contiene `{'conversion_factor': factor}`.

```python
from models.migration.Migration_Base import Migration_Base
import pandas as pd
from typing import Tuple


class D_BO_000000270_01(Migration_Base):
    def __init__(self):
        super().__init__()

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        # Insertar metrica y unidad_metrica antes de 'valor'
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value="moneda")
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value="BOB")

        factor = 1000000  # O el factor numérico correspondiente
        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000270_01
```

### Paso 4: Validar Localmente y Preparar Base de Datos
> [!WARNING]
> **PROHIBIDO CREAR TABLAS EN EL SERVIDOR DURANTE PRUEBAS LOCALES**:
> La creación de la tabla y del trigger en PostgreSQL es responsabilidad **exclusiva de la tarea `pre_load` de Airflow**. Nunca ejecutar `CREATE TABLE` en la base de datos real durante pruebas locales; de lo contrario, la tabla quedará vacía en la base antes de que el DAG corra.

1. **Resetear `migrated_to = NULL` si es la primera migración**:
   Muchos reportes heredan fechas falsas (`2026-08-24`, etc.) de la base vieja. Si el reporte nunca ha corrido en V2:
   ```sql
   UPDATE report SET migrated_to = NULL WHERE code = 'D_BO_..._XX';
   ```
2. **Probar `standard_report` y `process_numeric_column` en memoria**:
   ```python
   import sqlite3
   import pandas as pd
   from models.migration.M_BO_000000270.D_BO_000000270_01 import D_BO_000000270_01

   with sqlite3.connect("ruta/al/archivo.sqlite") as conn:
       df = pd.read_sql_query("SELECT * FROM D_BO_000000270_01", conn)

   robot = D_BO_000000270_01()
   df_dict, processed_df = robot.standard_report(df, conversion_factor=1)

   # Validar que valor sea la última columna
   assert processed_df.columns[-1] == "valor"
   print("Validación exitosa:", len(processed_df), "filas procesadas")
   ```
3. **Validar la interpolación del archivo SQL sin ejecutarlo**:
   ```python
   with open("models/migration/M_BO_000000270/D_BO_000000270_01.sql") as f:
       sql = f.read()
   formatted_sql = sql % ("ESQUEMA", "TABLA", "ESQUEMA", "TABLA")
   assert formatted_sql.count("%s") == 0
   ```

### Paso 5: Generar el DAG en Plataforma V2
Generar el archivo DAG correspondiente en `dags/migration/`:
```bash
python main-generate.py --migration M_BO_000000270
```
Verificar que se haya creado `dags/migration/M_BO_000000270.py`.

### Paso 6: Ejecutar en Airflow y Verificar
> [!CAUTION]
> **NUNCA PRESIONAR PLAY DIRECTO EN AIRFLOW UI**:
> Si se presiona el botón "Trigger DAG" sin parámetros, `dag_run.conf` estará vacío y el DAG fallará con `TypeError: 'NoneType' object is not iterable` al no encontrar el reporte.

**Disparo Directo sobre la Última Conversión (Recomendado):**
```bash
docker exec data-processing-platform-dev-airflow-worker-1 bash -c '
LAST_SQLITE=$(find /mnt/datos1/data_process/<PAIS>/<ID_PADRE>/ -name "*<ID_REPORTE>.sqlite" | sort | tail -n 1)
echo "Migrando: $LAST_SQLITE"
airflow dags trigger <DAG_PADRE> --conf "{\"code\": \"<ID_REPORTE>\", \"conversion_path\": \"$LAST_SQLITE\", \"id_conversion\": 1}"
'
```

**Disparo Manual con Parámetros Específicos:**
```bash
docker exec data-processing-platform-dev-airflow-worker-1 airflow dags trigger M_BO_000000270 \
  --conf '{"code": "D_BO_000000270_01", "id_conversion": 1, "conversion_path": "/ruta/al/archivo.sqlite"}'
```

**Verificación en Bases de Datos:**
- **`DATA_DB_<PAIS>`:** Verificar filas insertadas en `"<schema>"."<tabla>"`, UUIDs generados y valores multiplicados por el factor.
- **`platform_db`:** Verificar que `report.migrated_to` tenga la fecha de corte y que `public.migration` contenga el nuevo registro de auditoría.

---

## ⚠️ Gotchas y Errores Conocidos

1. **Esquemas con Mayúsculas y Acentos en PostgreSQL (`InvalidSchemaName`):**
   - En PostgreSQL, los identificadores sin comillas se convierten a minúsculas (`CREATE SCHEMA IF NOT EXISTS BCR` -> `bcr`).
   - Si la tabla fue definida con `"%s"."%s"`, el esquema buscará `"BCR"` respetando mayúsculas y fallará.
   - Asegurarse de que `CREATE SCHEMA IF NOT EXISTS "{storage_table[0]}"` siempre use **comillas dobles**.
2. **Actualización de `report` con `migrated_to IS NULL`:**
   - En PostgreSQL, `'2026-07-31' > NULL` evalúa a `NULL` (falsy).
   - En `dags/migration/sql/update_report.sql`, la condición debe incluir siempre `OR migrated_to IS NULL`.
3. **Error 404 en `trigger_product_dags`:**
   - Es totalmente esperado y normal si el DAG de producto (`S_...`) aún no está desplegado en desarrollo. La tarea finaliza en verde sin romper el pipeline.
