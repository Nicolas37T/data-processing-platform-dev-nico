# 🛠️ Especificaciones de Desarrollo: Módulo de Conversión (`Conversion_Base`)

Este documento establece las especificaciones de entrada, salida y reglas de desarrollo para robots de conversión en la **Plataforma V2**, implementando las funciones `extraction` y `validate_data_results`.

> 📌 **Reglas Generales de la Plataforma (V2):**
> * Código bajo estándares estrictos **PEP 8**.
> * Comentarios y `docstrings` estrictamente en **inglés**.
> * Clase nombrada idéntica al código del reporte heredando de `Conversion_Base`:
>   ```python
>   class D_BO_000000XXX_01(Conversion_Base):
>   ```
> * Manejo de excepciones con `traceback.print_exc()` y retorno de cadena vacía `""` en caso de error en `extraction`.

---

## 1. Función: `extraction`

### 📌 Descripción General
Localiza y extrae una tabla específica dentro de un documento fuente (PDF o Excel) a partir de palabras clave (`key_words`) y número de página. Transforma la tabla extraída en una tupla compuesta por un **diccionario de metadatos** y un **DataFrame normalizado/aplanado** (formato melted).

---

### 📥 Parámetros de Entrada
* `file_path` *(str)*: Ruta absoluta del archivo fuente descargado.
* `key_words` *(str)*: Palabras clave para identificar y validar la tabla en el documento.
* `template_path` *(str)*: Ruta a la plantilla de referencia (si aplica).
* `page_number` *(int)*: Número de página donde inicia la tabla en el documento ($\ge 1$).
* `format` *(str, opcional)*: Formato de fecha esperado (por defecto: `'%Y-%m-%d'`).

---

### 📤 Entregable / Valor de Retorno: Tupla `(metadatos_dict, df_melted)`

La función debe retornar exactamente una tupla de 2 elementos:

#### 1️⃣ Elemento 1: Diccionario de Metadatos (`dict`)
Contiene información contextual del documento. **No debe incluirse dentro del DataFrame**.
```python
{
    "file_name": "2026-08-19_boletin_diario.pdf",
    "titles": [
        "PRECIOS REFERENCIALES DE INSUMOS",
        "Reporte Diario de Cotizaciones"
    ],
    "page_number": 2
}
```

#### 2️⃣ Elemento 2: DataFrame Normalizado (`pd.DataFrame`)
Estructura totalmente aplanada en formato vertical (melted).
* 🚫 **Prohibido:** No incluir `file_name` ni `titles` como columnas del DataFrame.
* 🚫 **Prohibido:** No dejar valores numéricos formateados con texto ni símbolos de moneda en la columna `valor`.
* ✅ **Columnas obligatorias:** Jerarquía ordenada de niveles categóricos `[nv1, nv2, nv3, ..., fecha, valor]`.

##### Ejemplo de DataFrame Entregable:
| nv1 | nv2 | nv3 | nv4 | fecha | valor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| MAÍZ (Bs./qq.) | ORIGEN | Km 8 DOBLE VIA A LA GUARDIA | PRECIO | 2026-08-13 | 78 - 83 |
| CONSUMIDOR (Bs./Kg) | MERCADOS | MÍN. | MUTUALISTA | 2026-08-12 | 23.00 |
| CONSUMIDOR (Bs./Kg) | MERCADOS | PROM. | MUTUALISTA | 2026-08-11 | 24.50 |

> ⚠️ **Manejo de Excepciones:** Si ocurre cualquier error irrecuperable durante la lectura o extracción, la función debe imprimir el traceback y retornar una cadena vacía `""`:
> ```python
> except Exception as error:
>     print(f"Could not extract report from {file_path}: {error}")
>     traceback.print_exc()
>     return ""
> ```

---

## 2. Función: `validate_data_results`

### 📌 Descripción General
Valida la consistencia e integridad de los datos numéricos extraídos. Normaliza valores numéricos según el `decimal_separator` y verifica la coherencia aritmética de totales o promedios cuando el documento incluye sumatorias impresas.

---

### 📥 Parámetros de Entrada
* `dataframe` *(pd.DataFrame)*: DataFrame normalizado retornado por `extraction()`.
* `decimal_separator` *(str)*: Carácter separador decimal configurado en BD (`'.'` o `','`).
* `TOLERANCE` *(float, opcional)*: Margen de tolerancia admisible para diferencias de redondeo (por defecto: `6.0`).

---

### 📤 Entregable / Valor de Retorno (`bool`)

* `False` ➔ **Éxito / Sin Errores:** Todos los totales impresos coinciden con los calculados **O** la tabla no contenía totales/resúmenes para validar.
* `True` ➔ **Fallo de Validación / Error:** Existe una discrepancia entre totales calculados y totales impresos mayor a `TOLERANCE`.

---

## 3. Archivo SQLite de Referencia y `columns_to_review`

Al finalizar el desarrollo del modelo de conversión, se genera un archivo SQLite de referencia (`<CODE_REPORTE>.sqlite`) que contiene dos tablas internas:

1. **Tabla con los datos del reporte:** Nombrada exactamente igual al código del reporte (ej. `D_BO_000000481_01`).
2. **Tabla `columns_to_review`:** Tabla auxiliar utilizada por Airflow para detectar cambios estructurales inesperados entre ejecuciones:
   * **Nombre de tabla:** `columns_to_review` *(minúsculas, con `_`)*.
   * **Nombre de columna:** `column` *(en inglés, singular)*.
   * **Valores admitidos:** Únicamente columnas categóricas y `fecha` (ej. `fecha`, `nv1`, `nv2`, `nv3`, `nv4`, `nv8`).
   * 🚫 **NUNCA incluir `valor`:** Los montos numéricos cambian en cada publicación y generarían falsas alarmas de fallo de estructura.

---

## ✅ Criterios de Aceptación para Pull Requests
* [ ] Cumple estrictamente con **PEP 8**.
* [ ] Nombres de funciones, docstrings y comentarios dentro del código en **inglés**.
* [ ] Clase nombrada idéntica al archivo y código del reporte (`D_BO_...`).
* [ ] `extraction` retorna la tupla `(dict, pd.DataFrame)` con columnas `[nv1, ..., fecha, valor]`.
* [ ] `validate_data_results` retorna `False` cuando los datos son válidos y `True` si hay discrepancia.
* [ ] El archivo SQLite de referencia incluye la tabla `columns_to_review` sin la columna `valor`.
* [ ] El test unitario `models/conversion/tests/test_conversion.py` finaliza en **`OK`**.
