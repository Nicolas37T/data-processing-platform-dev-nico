# 🚀 Protocolo Express: Creación de DAGs de Migración en DATAX

Este documento define el procedimiento exacto, directo y sin rodeos que ejecuta el asistente cuando indicas:
> *"Hola, quiero crear un dag de migración para [CÓDIGO_REPORTE]"*

---

## ⚡ Filosofía de Ejecución Ultra-Rápida
1. **Cero teoría o rodeos**: Se generan directamente los archivos necesarios.
2. **Estricta estructura de 2 archivos por reporte** (sin `__init__.py` innecesario):
   - `models/migration/M_<PAIS>_<ID_PADRE>/D_<PAIS>_<ID_REPORTE>.sql`
   - `models/migration/M_<PAIS>_<ID_PADRE>/D_<PAIS>_<ID_REPORTE>.py`
3. **Comandos copy-paste listos para terminal**: Git, generación y trigger automático sobre la última conversión existente.

---

## 📋 Flujo Automatizado en 3 Pasos

### Paso 1: Generación Automática del Modelo (`.sql` y `.py`)

El asistente inspecciona el robot de conversión correspondiente (`models/conversion/C_.../D_..._XX.py`):
- Detecta los niveles jerárquicos (`nv1..nvN`) y columnas auxiliares (`emisor`, `titulo1`, etc.).
- Determina la métrica (`moneda`, `tasa`, `tipo_cambio`, `energia`, etc.) y la unidad métrica (`BOB`, `USD`, `%`, `MWh`, etc.).
- Identifica el factor de escala:
  - `1000000` si la fuente viene en "millones".
  - `1000` si viene en "miles".
  - `1` si ya viene en unidades completas.

Genera de inmediato:
1. **Archivo SQL DDL (`.sql`)**:
   ```sql
   CREATE TABLE IF NOT EXISTS "%s"."%s"
   (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     titulo1 text,
     nv1 text,
     nv2 text,
     nv3 text,
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

2. **Archivo Python (`.py`)**:
   ```python
   """Migration robot for report <CODIGO>."""

   import re
   from typing import Tuple
   import pandas as pd
   from models.migration.Migration_Base import Migration_Base


   class <CODIGO>(Migration_Base):
       """Migration robot for <CODIGO>."""

       def standard_report(self, dataframe: pd.DataFrame, conversion_factor: int) -> Tuple[dict, pd.DataFrame]:
           dataframe.columns = [re.sub(r"[\t\xa0]+", "", str(c)).strip() for c in dataframe.columns]

           for col in dataframe.columns:
               if col not in ["valor", "fecha"]:
                   dataframe[col] = dataframe[col].astype(str).str.strip()

           idx_valor = dataframe.columns.get_loc("valor")
           dataframe.insert(idx_valor, column="metrica", value="<METRICA>")
           dataframe.insert(idx_valor + 1, column="unidad_metrica", value="<UNIDAD>")

           factor = <FACTOR>
           return ({"conversion_factor": factor}, dataframe)


   Robot = <CODIGO>
   ```

---

### Paso 2: Subir a Git y Generar DAG en Servidor

El asistente te entrega los bloques de comandos exactos:

1. **En tu máquina local (Git Push):**
   ```bash
   git add models/migration/M_<PAIS>_<ID_PADRE>/
   git commit -m "feat(migration): implement robot M_<PAIS>_<ID_PADRE>"
   git push origin <tu_rama>
   ```

2. **En el servidor (`plat-dev-server`):**
   ```bash
   git pull origin <tu_rama>
   docker exec -it data-processing-platform-dev-airflow-worker-1 python include/main-generate.py
   ```
   - Opción: `3. Migration`
   - Opción: `1. Enter robot code(s)`
   - Ingresar código padre: `M_<PAIS>_<ID_PADRE>`

---

### Paso 3: Disparo Instantáneo sobre la Última Conversión

El asistente te proporciona el comando universal que localiza automáticamente el último `.sqlite` generado en el almacenamiento persistente (`/mnt/datos1/data_process/...`):

```bash
docker exec data-processing-platform-dev-airflow-worker-1 bash -c '
LAST_SQLITE=$(find /mnt/datos1/data_process/<PAIS>/<ID_PADRE>/ -type f -name "*_<CODIGO_REPORTE>.sqlite" | sort | tail -n 1)
echo "Migrando último archivo encontrado: $LAST_SQLITE"
airflow dags trigger <DAG_PADRE> --conf "{\"code\": \"<CODIGO_REPORTE>\", \"conversion_path\": \"$LAST_SQLITE\", \"id_conversion\": 1}"
'
```

---

## 🎯 Instrucción Clave para el Usuario
A partir de ahora, para crear cualquier migración solo escribe en el chat:
> **"Hola, quiero crear el dag de migración para [CÓDIGO(S)]"**

Y el asistente:
1. Inspeccionará la conversión.
2. Escribirá los archivos `.sql` y `.py` de una sola vez.
3. Te dará el bloque de comandos para git, `main-generate.py` y el trigger con `find` automático.
