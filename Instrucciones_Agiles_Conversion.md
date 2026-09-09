# 🤖 Modo Ágil de Creación y Verificación de DAGs de Conversión

Este protocolo define cómo interactuamos para verificar y poner en marcha los robots de conversión de manera rápida y automatizada.

---

## 🛑 Regla Fundamental de Trabajo
> **⚠️ ESTRICTAMENTE PROHIBIDO MODIFICAR LA LÓGICA INTERNA DEL ROBOT:**
> Si el robot tiene errores de extracción, índices rotos, fallos de cálculo o datos faltantes:
> 1. **NO** reescribimos el algoritmo.
> 2. **SÍ** redactamos inmediatamente el mensaje técnico detallado para devolver el robot al freelancer/pasante.

---

## ⚡ Flujo de Interacción Automatizado

Para cada reporte nuevo, solo necesitas pasarme:
1. **Código del reporte** (ej: `D_BO_000000577_01`).
2. **Código del robot** que te entregó el freelancer.
3. **Fila del reporte en `platform_db`** (copiada de DBeaver/PgAdmin).
4. **Nombre del archivo de muestra** en `models/conversion/C_.../`.

---

## 🚀 Lo que yo haré automáticamente paso a paso:

### 1️⃣ Paso 4: Estandarización de Encabezados y Guardado
- Guardar el archivo en `models/conversion/C_.../D_..._0X.py`.
- Asegurar los imports estándar (`Conversion_Base`, `conversion_tools`).
- Nombrar la clase exactamente igual al reporte: `class D_BO_000000XXX_0X(Conversion_Base):`.
- Asegurar que `extraction` retorne `""` en bloques `except`.

### 2️⃣ Paso 5: Validación de Base de Datos
- Revisar que `storage_table`, `replacement_table`, `key_words` y `decimal_separator` cumplan el estándar.
- Darte el `UPDATE SQL` exacto y listo para ejecutar en `platform_db`.

### 3️⃣ Paso 6: Configuración y Ejecución del Test Unitario
- Configurar automáticamente `REPORT_CODE` y `FILE_PATH` en `test_conversion.py`.
- Comentar `text_match` para aislar la prueba de extracción.
- Darte el comando Docker de ejecución:
  ```bash
  docker exec -it data-processing-platform-dev-airflow-worker-1 python -m unittest models/conversion/tests/test_conversion.py
  ```
- **Si falla la extracción:** Te redacto de inmediato el reporte de observaciones para el freelancer.
- **Si pasa (`OK`):** Avanzamos directo a los pasos 7 y 8.

### 4️⃣ Pasos 7 y 8: Reemplazos y Creación de `columns_to_review`
- Descomentar `text_match` para poblar la tabla en `DATA_DB_BO_AUX`.
- Inspeccionar las columnas del `.sqlite` generado y darte el comando `python -c "..."` listo con las columnas categóricas (excluyendo montos variables y comodines como `'-'`).

### 5️⃣ Pasos 9 al 12: Despliegue y Validación en Airflow
- Darte el `UPDATE SQL` para registrar `converted_report_path`.
- Guiarte en `include/main-generate.py` para crear el wrapper `dags/conversion/C_...py`.
- Darte los comandos `git`, `unpause` y `trigger` con el payload JSON formateado para probar en Airflow.

---

### 📩 Plantilla Estándar para Devolución al Freelancer:
```markdown
**Asunto:** Corrección requerida en robot {REPORT_CODE}

Hola,

Al ejecutar las pruebas unitarias para el robot **`{REPORT_CODE}`**, se encontraron las siguientes observaciones:

### 🔍 Error detectado:
{DESCRIPCION_DEL_ERROR}

### 🛠️ Corrección requerida:
{INSTRUCCIONES_EXACTAS}

Por favor realiza los ajustes y valida que el test unitario finalice en **`OK`**.
```
