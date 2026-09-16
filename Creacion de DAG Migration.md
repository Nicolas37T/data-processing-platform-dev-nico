# 📦 Manual Definitivo: Creación e Implementación de un DAG de Migración (Plataforma V2)

Este manual documenta el **flujo de trabajo completo para robots de Migración (`M_...`)** en la **Plataforma V2** (Airflow 3, PostgreSQL 17, servidor `10.0.0.16`), cubriendo tanto reportes migrados de la fábrica anterior como reportes nuevos desde cero.

---

## 🧭 Los Dos Escenarios de Trabajo

Antes de iniciar, identifica en cuál de los dos escenarios te encuentras:

```
                  ¿El reporte ya existía en la fábrica anterior?
                                    |
                    +---------------+---------------+
                    |                               |
                   SÍ                              NO
                    |                               |
         [ESCENARIO A: MIGRADO]            [ESCENARIO B: NUEVO]
         - Copiar archivos .py y .sql     - Crear estructura desde 0
         - Comparar con nuevo .sqlite     - Crear standard_report()
         - Ajustar columnas / nvN         - Diseñar DDL .sql completo
                    |                               |
                    +---------------+---------------+
                                    |
                           [PASOS COMUNES]
                  - Validar en platform_db
                  - Prueba unitaria / local
                  - Generar DAG (main-generate.py)
                  - Probar y validar en Airflow
```

- **Escenario A (Reporte Preexistente / Migrado):** Ya se cuenta con el código `.py` y el esquema `.sql`. Solo se copian a `models/migration/M_.../`, se revisa si la nueva conversión añadió niveles (ej. `nv5`), se actualiza el `.sql` y el `.py` para reflejar esos cambios y se procede.
- **Escenario B (Reporte Nuevo):** Se implementa la clase desde cero, analizando el `.sqlite` de conversión para detectar moneda, magnitud y unidad de medida.

---

## **Paso 1: Configurar la Base de Datos (`platform_db` ➔ tabla `report`)**

Conéctate a `platform_db` (en `10.0.0.16:5434`) y verifica la configuración del reporte:

```sql
SELECT id_report, code, name, storage_table, decimal_separator, 
       conversion_factor, load_scope, migrated_to, "isActive"
FROM report 
WHERE code = 'D_BO_000000270_01';
```

### 📐 Campos obligatorios para Migración:
- **`storage_table`:** Formato estricto `ESQUEMA;TABLA` en la base de datos de almacenamiento (`DATA_DB_{COUNTRY}`).
  - Ejemplo: `'MinisterioEconomíaFinanzasPublicas;DATA_D_BO_000000270_01'`
  - 🚫 *Nunca poner rutas de archivos ni nombres con espacios sin formato*.
- **`load_scope`:** Controla qué registros limpia `pre_load` antes de insertar:
  - `""` (vacío / por defecto): Elimina únicamente los registros dentro del rango de fechas de la presente carga (`fecha >= min AND fecha <= max`).
  - `'current_year'`: Elimina registros del año en curso (`fecha >= 'YYYY-01-01'`).
  - `'all'`: Elimina todos los registros de la tabla previa copia de seguridad.
- **`decimal_separator`:** `.` (punto) o `,` (coma). 
  > ⚠️ **Atención:** Revisa cómo vienen formateados los valores en el `.sqlite` de conversión. Si vienen como `19.91 %` o `1,451,608.31`, el separador decimal es `.` (punto), no `,`. Una discrepancia aquí causará que `process_numeric_column` devuelva `NaN` o valores multiplicados por 100.
- **`conversion_factor`:** Factor base (generalmente `1` o el valor inicial).
- **`migrated_to`:** **ESTADO INICIAL OBLIGATORIO**:
  - Si el reporte **nunca ha sido migrado en la Plataforma V2** (`public.migration` vacía para este reporte), su valor **DEBE ser `NULL`**.
  - Si arrastra una fecha espuria heredada de la base vieja (ej. `2026-08-24`, `1900-01-01`), **resetealo inmediatamente**:
    ```sql
    UPDATE report SET migrated_to = NULL WHERE code = '<CODIGO_REPORTE>';
    ```
- **`isActive`:** `TRUE`.

---

## **Paso 2: Estructura de Directorios en `models/migration/`**

Crea el directorio correspondiente al robot agrupador (prefijo `M_` + código padre):

```
models/migration/M_BO_000000270/
├── __init__.py               <-- Obligatorio para importación dinámica
├── D_BO_000000270_01.py      <-- Lógica de estandarización Python
└── D_BO_000000270_01.sql     <-- DDL de la tabla en PostgreSQL
```

> [!IMPORTANT]
> - La carpeta lleva el prefijo **`M_`** (ej. `M_BO_000000270`).
> - Los archivos internos llevan el **código exacto del reporte** (ej. `D_BO_000000270_01.py` y `D_BO_000000270_01.sql`).

---

## **Paso 3: Implementar o Estandarizar el Código Python (`D_..._0X.py`)**

1. Heredar de `from models.migration.Migration_Base import Migration_Base`.
2. Asignar el nombre de clase idéntico al código del reporte y alias `Robot = D_BO_...`.
3. Implementar `def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]`:
   - Limpiar caracteres de espacio o tabs invisibles en nombres de columnas si provienen de conversión (ej. `"Emisor\t\xa0"` ➔ `"emisor"`).
   - Insertar `'metrica'` y `'unidad_metrica'` **ANTES de `'valor'`**.
   - Garantizar que `'valor'` sea siempre la **última columna** (`df.columns[-1]`), pues de ello depende `process_numeric_column()`.
   - Retornar `({'conversion_factor': factor}, dataframe)`.

El archivo Python debe heredar de `Migration_Base` e implementar la función **`standard_report`**:

```python
import re
import pandas as pd
from typing import Tuple
from models.migration.Migration_Base import Migration_Base


class D_BO_000000270_01(Migration_Base):
    """Migration robot for D_BO_000000270_01."""

    def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
        """
        Enriquece el DataFrame con metadatos de metrica y unidad_metrica,
        y determina el factor de conversion para llevar los valores a unidades enteras.
        """
        # 1. Limpieza de nombres de columna (opcional si vienen con caracteres especiales)
        # dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

        # 2. Definir o detectar la unidad métrica y factor de magnitud
        metric_type = "moneda"
        metric_unit = "BOB"
        factor = 1  # Si viene en miles usar 1000, en millones 1000000

        # 3. Insertar columnas 'metrica' y 'unidad_metrica' antes de 'valor'
        # El DataFrame de conversion termina en: [..., 'fecha', 'valor']
        idx_valor = dataframe.columns.get_loc("valor")
        dataframe.insert(idx_valor, column="metrica", value=metric_type)
        dataframe.insert(idx_valor + 1, column="unidad_metrica", value=metric_unit)

        # 4. Retornar el factor de conversión en un dict y el DataFrame enriquecido
        return ({"conversion_factor": factor}, dataframe)


Robot = D_BO_000000270_01
```

### 📐 Reglas de Oro de `standard_report`:
1. **No alterar filas ni cálculos:** Su único rol es enriquecer con metadatos (`metrica`, `unidad_metrica`) y declarar el `conversion_factor`.
2. **Posición de columnas:** `'metrica'` y `'unidad_metrica'` deben quedar inmediatamente antes de `'valor'`.
3. **Multiplicación automática:** No necesitas multiplicar `valor * factor` manualmente; el método base `process_numeric_column` de `Migration_Base` lo hace automáticamente con el factor que retornes en el diccionario.

---

## **Paso 4: Crear o Actualizar el Esquema SQL (`D_..._0X.sql`)**

El archivo `.sql` define la estructura de la tabla permanente en PostgreSQL (`DATA_DB_{COUNTRY}`). Contiene placeholders `%s."%s"` que Airflow reemplaza dinámicamente con el esquema y nombre de tabla configurados en `storage_table`.

> [!IMPORTANT]
> - ❌ **PROHIBIDO `WITH (OIDS=FALSE)`:** En PostgreSQL 12+ esta cláusula fue removida y provocará error de sintaxis.
> - La plantilla interpola exactamente **4 marcadores `%s`**: `(esquema, tabla, esquema, tabla)` para la creación de la tabla y la vinculación del trigger.

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

-- Trigger para actualizar fecha_modificacion en cada UPDATE
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

> [!WARNING]
> **Sincronización con Conversión:** Las columnas del `.sql` deben coincidir exactamente con las que genera el `.sqlite` de conversión. Si la conversión tiene `nv1` hasta `nv5`, el `.sql` **debe** incluir `nv1 text, nv2 text, nv3 text, nv4 text, nv5 text`.

---

## **Paso 5: Prueba Local de Migración (Fin del Trabajo Local)**

> [!CAUTION]
> **PROHIBIDO CREAR LA TABLA EN POSTGRESQL DURANTE TESTS LOCALES**:
> La creación de la tabla y del trigger en `DATA_DB_<PAIS>` es responsabilidad **única de la tarea `pre_load` en Airflow**. Nunca ejecutes `CREATE TABLE` manualmente contra la base de datos real; de lo contrario, la tabla quedará vacía antes de que el DAG corra.

Antes de desplegar en Airflow, ejecuta una prueba 100% en memoria contra el `.sqlite` generado en conversión:

```python
import sqlite3
import pandas as pd
from models.migration.M_BO_000000270.D_BO_000000270_01 import D_BO_000000270_01

robot = D_BO_000000270_01()
df_sqlite = robot.read_table("models/conversion/C_BO_000000270/D_BO_000000270_01.sqlite")

meta, df_std = robot.standard_report(df_sqlite, conversion_factor=1)
print("Columnas:", df_std.columns.tolist())
print("Factor detectado:", meta["conversion_factor"])
print(df_std.head(3))

# Validar interpolación sintáctica del SQL sin tocar la base de datos
with open("models/migration/M_BO_000000270/D_BO_000000270_01.sql") as f:
    sql_text = f.read()
sql_check = sql_text % ("ESQUEMA", "TABLA", "ESQUEMA", "TABLA")
assert sql_check.count("%s") == 0
```

Verifica:
- Que existan las columnas `'metrica'` y `'unidad_metrica'`.
- Que `'valor'` sea estrictamente la última columna (`df_std.columns[-1] == 'valor'`).
- Que la interpolación SQL no tenga errores.

> [!IMPORTANT]
> 🛑 **LÍMITE DEL TRABAJO LOCAL:**
> En tu máquina local de desarrollo el flujo concluye **AQUÍ en el Paso 5**.
> **NO generes el DAG localmente** ni incluyas archivos dentro de `dags/migration/` en tu commit. El archivo `dags/migration/M_...py` se genera **exclusivamente en el servidor de producción** mediante `main-generate.py`.

---

## **Paso 6: Commit, Push y Generación del DAG en el Servidor**

1. **En tu máquina local:** Haz commit y push de la carpeta del modelo:
   ```bash
   git add models/migration/M_BO_000000270/
   git commit -m "feat(migration): implement robot M_BO_000000270"
   git push origin <tu_rama>
   ```

2. **En el servidor (`10.0.0.16`):**
   - Actualiza los cambios:
     ```bash
     git pull origin <tu_rama>
     ```
   - Genera el DAG wrapper en el servidor con el generador unificado:
     ```bash
     docker exec -it data-processing-platform-dev-airflow-worker-1 python include/main-generate.py
     ```
     1. Selecciona la opción **`3. Migration`**.
     2. Selecciona la opción **`1. Enter robot code(s)`**.
     3. Ingresa el código padre: **`M_BO_000000270`**.
     4. Se generará automáticamente el wrapper en `dags/migration/M_BO_000000270.py`.

---

## **Paso 7: Probar el DAG en Airflow (Trigger Manual)**

A diferencia de Conversión, el DAG de migración recibe los datos de la conversión terminada:

```bash
docker exec data-processing-platform-dev-airflow-worker-1 airflow dags trigger M_BO_000000270 \
  --conf '{"code": "D_BO_000000270_01", "conversion_path": "/mnt/datos1/data_process/BO/D_BO_000000270/2026/2026-07/2026-07-31_D_BO_000000270_01.sqlite", "id_conversion": 1}'
```

### ⚠️ Parámetros obligatorios en `--conf`:
- **`"code"`**: Código del reporte a migrar (`D_BO_000000270_01`).
- **`"conversion_path"`**: Ruta al archivo `.sqlite` procesado en conversión.
- **`"id_conversion"`**: ID numérico del registro de conversión en `platform_db`.

---

## **Paso 8: Validar la Ejecución Completa (Puntos de Control)**

Revisa que todas las tareas terminen en **Verde (Success)**:
`get_migration_data` ➔ `pre_load` ➔ `load` ➔ `post_load` ➔ `record_migration` ➔ `update_report` ➔ `trigger_dags`.

Valida 4 puntos críticos:

1. **Tabla de Almacenamiento creada e insertada (`DATA_DB_{COUNTRY}`):**
   ```sql
   SELECT COUNT(*), MIN(fecha), MAX(fecha) 
   FROM "MinisterioEconomíaFinanzasPublicas"."DATA_D_BO_000000270_01";
   ```
   *(Deben aparecer los registros insertados con su UUID, metrica, unidad_metrica y valores escalados)*.

2. **Registro de Auditoría en la tabla `migration` (`platform_db`):**
   ```sql
   SELECT id_migration, id_report, migrated_to, migration_date 
   FROM migration 
   WHERE id_report = 455 
   ORDER BY id_migration DESC LIMIT 1;
   ```

3. **Actualización de `migrated_to` en la tabla `report` (`platform_db`):**
   ```sql
   SELECT code, migrated_to, conversion_factor 
   FROM report 
   WHERE code = 'D_BO_000000270_01';
   ```
   *(El campo `migrated_to` debe tener la fecha del documento, ej: `2026-07-31`)*.

4. **Encadenamiento a Product:**
   Si existen modelos de producto asociados en `data_base_report`, la tarea `trigger_product_dags` disparará automáticamente los DAGs `DB_...`.

---

## 💡 Diagnóstico y Solución de Problemas Comunes

### 1. `FileNotFoundError: SQL file doesn't exists` en `pre_load`
- **Causa:** El archivo `.sql` no se llama exactamente igual al código del reporte o no está en la carpeta del modelo.
- **Solución:** Asegurar que exista `models/migration/M_.../D_..._01.sql`.

### 2. `migrated_to` permanece en blanco / `NULL` tras ejecución exitosa
- **Causa:** En `dags/migration/sql/update_report.sql`, la condición es `'fecha' > migrated_to`. En PostgreSQL, `'fecha' > NULL` evalúa a `NULL` (falsy) y no actualiza nada.
- **Solución:** Asegurar que `update_report.sql` contenga:
  ```sql
  AND ('{{ ti.xcom_pull(task_ids='pre_load', key='converted_to')}}' > migrated_to OR migrated_to IS NULL);
  ```

### 3. `ProgrammingError: schema "..." does not exist` en `pre_load`
- **Causa:** Sensibilidad a mayúsculas en PostgreSQL. Si `storage_table` define un esquema con mayúsculas (ej. `"ASFI"` o `"BCB"`), pero en la base de datos se creó sin comillas (`CREATE SCHEMA ASFI`), PostgreSQL lo guarda en minúsculas (`asfi`). Cuando el script intenta crear la tabla con `CREATE TABLE "ASFI"."..."`, falla al no encontrar el esquema con mayúsculas exactas.
- **Solución:** Asegurar que el esquema en `DATA_DB_<PAIS>` exista con comillas dobles respetando la mayúscula (`CREATE SCHEMA IF NOT EXISTS "ASFI";`), y que en `dags/templates/migration_template.py` se use `CREATE SCHEMA IF NOT EXISTS "{storage_table[0]}"` con comillas dobles.

### 4. Discrepancia en `post_load` (`notify_post_load_error`)
- **Causa:** La resta `num_records_after - num_records_before` no coincide con los registros migrados. Suele ocurrir si `load_scope` borró registros duplicados o si falló el `INSERT`.
- **Solución:** Verificar que el `.sqlite` no contenga registros corruptos y que la tabla no tenga restricciones `UNIQUE` conflictivas.

### 5. Desalineación de columnas entre SQLite y PostgreSQL
- **Causa:** El `.sqlite` tiene columnas nuevas (ej. `nv5`) que no están definidas en el `.sql` de creación, o nombres con caracteres ocultos (ej. `Emisor\t\xa0`).
- **Solución:** Limpiar los nombres de columnas en `standard_report` y agregar las columnas faltantes al `.sql` y a la tabla existente en PostgreSQL con `ALTER TABLE "esquema"."tabla" ADD COLUMN nv5 text;`.

---

¡Con esta guía tienes el protocolo definitivo y blindado para todos los DAGs de migración! 🚀
