---
trigger: always_on
---

# 📘 Estándares Oficiales de Desarrollo - DATAX Platform

Este documento define los estándares obligatorios de arquitectura, código, calidad y control de versiones que deben cumplir todos los robots de **Conversión** y **Descarga** en `data-processing-modules`.

---

## 1. 🔄 Robots de Conversión (`C_...` / `D_..._XX`)

### 1.1. Regla de Oro de la Clase Robot (Estricta)
> [!IMPORTANT]
> **REGLA ESTRICTA DE 2 MÉTODOS**: La clase `Robot` (o clase con código de reporte) debe contener **ÚNICA Y EXCLUSIVAMENTE DOS MÉTODOS**:
> 1. `def extraction(self, file_path: str, key_words: str, template_path: str = "", page_number: int = 1, format: str = "%Y-%m-%d") -> tuple:`
> 2. `def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str = ",", TOLERANCE: float = 6.0) -> bool:`
>
> ❌ **PROHIBIDO**:
> - NO definir constructor `__init__`.
> - NO definir métodos auxiliares en `self` (ej. `self._limpiar()`).
> - Cualquier función auxiliar DEBE declararse como **función anidada dentro de `extraction()`** o a nivel de módulo antes de la clase.

### 1.2. Regla de Jerarquías de Niveles (`nv1` a `nvN`) y Esquema Mental de Colores
Cuando un reporte presenta jerarquías visuales o contables, el mapeo debe seguir el orden maestro:
- **`nv1` (Naranja - Raíz / Total General)**: El concepto o título maestro del reporte (ej. `Deuda Pública Interna Total del TGN`). Debe estar presente en **todas las filas**.
- **`nv2` (Celeste - Sector / Agrupador Mayor)**: Los sectores principales (ej. `Sector Público Financiero`, `Sector Privado`). La fila del Total General lleva `None` en `nv2`.
- **`nv3` (Verde - Entidad o Mercado)**: Las instituciones o subsectores (ej. `BCB`, `Fondos`, `AFPs`, `Tesoro directo`).
- **`nv4` (Amarillo - Instrumento)**: Los instrumentos o tipos de valor (ej. `Bts-Neg.`, `Deuda Hist-LT "A"`, `BTs-No Neg.`).
- **`nv5` (Sub-instrumento específico)**: Se utiliza si existe una subdivisión adicional (ej. `spf_bts-no neg.`, `Bonos "C"`). Si el instrumento concluye en `nv4`, `nv5` es `None`.

### 1.3. Contrato de Retorno de `extraction()`
Retorna una tupla `(metadata_dict, df_melted)`:
1. `metadata_dict`:
   ```python
   {
       "file_name": os.path.basename(file_path),
       "titles": ["Título Oficial del Reporte"],
       "page_number": int(page_number)
   }
   ```
2. `df_melted`:
   - Columnas jerárquicas: `nv1` .. `nvN` (todas strings o `None`).
   - Columna `fecha`: Penúltima columna, formato estricto `YYYY-MM-DD`.
   - Columna `valor`: Última columna, estrictamente numérica (`int` o `float`).

### 1.4. Reconciliación Matemática en `validate_data_results()`
> [!IMPORTANT]
> Esta función valida que el aplanamiento de datos sea matemáticamente exacto:
> $$\sum 	ext{Instrumentos Amarillos} = \sum 	ext{Sectores Celestes} = 	ext{Total General Naranja}$$
>
> **Lógica estándar**:
> 1. Agrupar por cada `fecha` de corte mensual en el DataFrame.
> 2. Extraer el Total General esperado (fila donde `nv2.isna()`).
> 3. Sumar los instrumentos individuales componentes (filas donde `nv2.notna()`).
> 4. Comprobar que $| \sum 	ext{componentes} - 	ext{Total} | \le 	ext{TOLERANCE}$ ($6.0$).
> 5. **Retorno booleano**:
>    - `return False`: Validación **EXITOSA** (sin errores, datos consistentes).
>    - `return True`: Se detectó una **INCONSISTENCIA** o error numérico.

---

## 2. 📥 Robots de Descarga (`D_...`)

### 2.1. Métodos Obligatorios
```python
class Robot:
    def get_file_url(self, specific_url, navigation_path, download_path, user_key=None) -> list:
        pass

    def compare_files(self, file_path_1, file_path_2) -> bool:
        pass

    def verify_url(self, url) -> bool:
        pass
```

---

## 3. 🚚 Robots de Migración (`M_...` / `D_..._XX`)

### 3.1. Estructura de Archivos
Ubicados en `models/migration/M_<PAIS>_<ID_BASE>/`:
1. `D_<PAIS>_<ID_REPORTE>.py`: Clase ejecutora que hereda de `Migration_Base`.
2. `D_<PAIS>_<ID_REPORTE>.sql`: DDL de PostgreSQL con tabla y trigger.

### 3.2. Reglas del Archivo SQL (`.sql`)
- La plantilla `migration_template.py` interpola exactamente 4 parámetros: `(schema, table, schema, table)`.
- Clave primaria obligatoria: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- Columnas de auditoría:
  - `fecha_creacion date DEFAULT CURRENT_DATE`
  - `fecha_modificacion timestamp DEFAULT CURRENT_TIMESTAMP`
  - `observations text`
- Columnas de métricas: `metrica character varying(255)`, `unidad_metrica character varying(255)`.
- Trigger de auditoría: función `actualizar_fecha_modificacion()` y `CREATE OR REPLACE TRIGGER trigger_actualizar_fecha_modificacion BEFORE UPDATE ON "%s"."%s" FOR EACH ROW EXECUTE FUNCTION actualizar_fecha_modificacion();`.
- ❌ **PROHIBIDO**: `WITH (OIDS=FALSE)` (removido en PostgreSQL moderno).

### 3.3. Reglas de la Clase Python (`.py`)
- Heredar de `from models.migration.Migration_Base import Migration_Base`.
- El nombre de la clase debe ser idéntico al código del reporte (ej. `class D_BO_000000270_01(Migration_Base):`).
- Asignar alias `Robot = D_BO_...`.
- Implementar `standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]`:
  - Insertar `metrica` y `unidad_metrica` antes de `valor`, garantizando que `valor` permanezca como la **última columna** (`df.columns[-1]`).
  - Retornar `(df_dict, df)` con `{'conversion_factor': factor}`.

### 3.4. Reglas Operativas de Ejecución y PostgreSQL
- **Estado Inicial de `migrated_to`:** Si un reporte nunca ha sido migrado en V2 (`public.migration` vacía para ese reporte), `report.migrated_to` **DEBE ser `NULL`**. Si tiene fechas espurias de la base vieja (ej. `2026-08-24`), deben resetearse a `NULL` antes de desplegar.
- **No crear tablas en base real durante tests locales:** Las pruebas locales deben ser en memoria o sintácticas. La creación de la tabla y del trigger en PostgreSQL es responsabilidad **exclusiva de `pre_load` en Airflow**.
- **Comillas en Esquemas:** Los esquemas deben crearse y consultarse con comillas dobles `"{storage_table[0]}"` para evitar que PostgreSQL los convierta a minúsculas y rompa la sensibilidad a mayúsculas.
- **Manejo de NULL en Reportes:** En consultas SQL como `update_report.sql`, siempre incluir `OR migrated_to IS NULL` (y `OR converted_to IS NULL`) debido a la lógica trivaluada de PostgreSQL donde `'fecha' > NULL` devuelve `NULL`.
- **Ejecución en Airflow:** NUNCA disparar migración sin configuración. Usar siempre `Trigger DAG w/ config` o `--conf '{"code": "...", "id_conversion": ..., "conversion_path": "..."}'`.

---

## 4. 🛡️ Autosuficiencia y Aprendizaje en `data-processing-modules`
- Los desarrolladores en este repositorio **NO requieren ni tienen acceso a `data-processing-platform-dev`** ni bases de datos de red interna.
- Todo el código debe importar herramientas locales:
  ```python
  from conversion_tools import to_numeric_datax
  from download_tools import createDirectoryStruct
  ```
- Para estudiar robots aprobados y resolver dudas, consultar las ramas remotas del repositorio:
  ```bash
  git fetch origin
  git branch -r
  git show origin/<nombre-rama>:robot.py
  ```
  Ramas de referencia destacadas:
  - `origin/nicolas/D_BO_000000270_01`: Jerarquía multinivel de 5 niveles, corte temporal y validación matemática de sumas.
  - `origin/andresrevollo/D_BO_000000485_01`: Extracción tabular y regex de cabeceras.
  - `origin/cristhian/D_BO_000000418_02`: Fechas dinámicas y validación con sumatorias.
