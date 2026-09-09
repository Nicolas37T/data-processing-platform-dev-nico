# 🛠️ Especificaciones de Desarrollo: Descarga Tipo IV (`file_download_type_iv`)

> 📌 **Reglas Generales de la Plataforma (V2):**
> * Código bajo estándares estrictos **PEP 8**.
> * Comentarios y `docstrings` estrictamente en **inglés**.
> * Clase nombrada idéntica al código del robot heredando de `Download_Base`:
>   ```python
>   class D_BO_000000XXX(Download_Base):
>   ```
> * **Atención:** La comparación y filtrado respecto a `updated_to` no se realiza en una función `compare_files()`, sino de forma posterior en el DAG mediante el operador `store_new_data()`.

---

## 1. Función: `get_data`

### 📌 Descripción General
Realiza la descarga masiva de todos los archivos pertenecientes a un repositorio o portal (ej. Datasur, SNIS, portales de comercio exterior), utilizando concurrencia o asincronismo si es necesario. Deposita todos los archivos en la carpeta `<path>/tmp` y devuelve **únicamente la ruta absoluta** del directorio temporal donde residen los archivos.

> 🧹 **Gestión de Limpieza:** Al iniciar la ejecución, la carpeta `<path>/tmp` debe eliminarse (si existe) y recrearse para asegurar que no queden archivos residuales de ejecuciones previas.

---

### 📥 Parámetros de Entrada
* `main_url` *(str)*: URL principal del portal o servicio de descarga masiva.
* `path` *(str)*: Directorio base donde se creará la carpeta `tmp` con todos los archivos descargados.
* `updated_to` *(str)*: Fecha de referencia (`YYYY-MM-DD`). Se utiliza internamente para definir el año o parámetro de inicio de la descarga masiva.
* `format` *(str, opcional)*: Formato de la fecha `updated_to` (por defecto: `'%Y-%m-%d'`).

---

### 📤 Entregable / Valor de Retorno (`str`)

* **En caso de éxito / descarga completada:** Cadena de texto con la **ruta absoluta del directorio `tmp`** que contiene todos los archivos descargados:
  ```python
  "/mnt/datos1/downloaded_files/tmp"
  ```

* **Si no hay archivos descargados / Error / Excepción:** Cadena de texto vacía `''` (o `None`).

---

### 🚨 Reglas Críticas para `get_data`:

1. **Nombrado Obligatorio de Archivos con Prefijo de Fecha:**
   * Cada archivo descargado dentro de la carpeta temporal debe iniciar obligatoriamente con la fecha en formato `YYYY-MM-DD` (ej. `2026-08-20_datos_comercio.csv`).
   * *El test unitario valida explícitamente:* `r'^\d{4}-\d{2}-\d{2}'`.

2. **Descarga Masiva Completa:**
   * La función debe descargar todos los lotes de datos desde el punto de inicio indicado por `updated_to` hasta la fecha más reciente disponible.

---

## ✅ Criterios de Aceptación para Pull Requests
* [ ] Cumple estrictamente con **PEP 8**.
* [ ] Documentación interna y comentarios en **inglés**.
* [ ] Recrea limpiamente la carpeta `<path>/tmp` al iniciar.
* [ ] Los archivos dentro de `tmp` inician con la fecha en formato `YYYY-MM-DD_...`.
* [ ] Retorna únicamente el *string* con la ruta absoluta del directorio temporal (o `''` en caso de fallo).
* [ ] El test unitario `models/download/tests/test_download_type_iv.py` finaliza en **`OK`**.
