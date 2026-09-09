# 🛠️ Especificaciones de Desarrollo: Descarga Tipo I (`file_download_type_i`)

> 📌 **Reglas Generales de la Plataforma (V2):**
> * Código bajo estándares estrictos **PEP 8**.
> * Comentarios y `docstrings` estrictamente en **inglés**.
> * Clase nombrada idéntica al código del robot heredando de `Download_Base`:
>   ```python
>   class D_BO_000000XXX(Download_Base):
>   ```
> * Estructura estricta de **SOLO 2 métodos**: `get_file_url` y `compare_files`.

---

## 1. Función: `get_file_url`

### 📌 Descripción General
Navega el sitio web del portal origen (generalmente mediante automatización con Playwright o peticiones HTTP), identifica los enlaces de descarga de los archivos, aplica filtros opcionales (palabras clave o fechas visibles en el portal) y extrae **todas las URLs** correspondientes a publicaciones más recientes que `updated_to`.

---

### 📥 Parámetros de Entrada
* `main_url` *(str)*: URL principal donde se listan o publican los archivos.
* `updated_to` *(str)*: Fecha de referencia en la BD (`YYYY-MM-DD`). Se buscan archivos con fecha estrictamente posterior.
* `key_words` *(str, opcional)*: Palabras clave para filtrar enlaces específicos (ej: `"mensual"`, `"boletin"`).
* `format` *(str, opcional)*: Formato de fecha para `updated_to` (por defecto: `'%Y-%m-%d'`).

---

### 📤 Entregable / Valor de Retorno (`list[str]`)

* **En caso de éxito / hallazgos:** Lista de cadenas (`list[str]`) con **todas** las URLs de descarga encontradas.
  ```python
  [
      "https://sitio.com/archivos/reporte_2026_01.xlsx",
      "https://sitio.com/archivos/reporte_2026_02.xlsx",
      "https://sitio.com/archivos/reporte_2026_03.xlsx"
  ]
  ```
* **Si no hay archivos nuevos / Error / Excepción:** Lista vacía `[]`.

---

### 🚨 Reglas Críticas para `get_file_url`:

1. **Descarga Histórica Completa (🚫 Prohibido `max()`):**
   * El robot debe devolver **TODAS las URLs** de los archivos publicados entre `updated_to` y hoy.
   * **Ejemplo:** Si el robot no se ejecutó durante 2 meses y hay 60 boletines diarios nuevos, la lista devuelta debe contener las 60 URLs.
   * ❌ **Error típico:** Calcular `max(...)` para quedarse solo con el último archivo. Esto provoca la pérdida irreversible de todos los datos intermedios.

2. **Gestión de Recursos de Playwright:**
   * Cerrar siempre el navegador en un bloque `finally`:
     ```python
     with sync_playwright() as playwright:
         browser = playwright.chromium.launch(headless=True)
         try:
             # navegación y extracción
             ...
         finally:
             browser.close()
     ```

3. **Filtrado en Web:**
   * Si la web muestra fechas en el texto/enlaces, filtrar contra `reference_date = format_date(updated_to, format)`.
   * Si la web **no** muestra fechas, retornar todas las URLs encontradas para que `compare_files` filtre por el contenido interno de cada documento.

---

## 2. Función: `compare_files`

### 📌 Descripción General
Recibe los archivos descargados por la plataforma en carpetas temporales (`tmp`), lee el contenido interno de cada documento (Excel, PDF, ZIP) para extraer la **fecha exacta de publicación o referencia**, y filtra aquellos cuya fecha interna sea estrictamente posterior a `updated_to`.

---

### 📥 Parámetros de Entrada
* `files_paths` *(list[dict])*: Lista de diccionarios provista por el orquestador con las rutas de los archivos descargados.
  * *Estructura de cada elemento:*
    ```python
    {
        "tmp_path": "/mnt/datos1/downloaded_files/tmp/archivo.xlsx",
        "download_url": "https://sitio.com/archivos/archivo.xlsx"
    }
    ```
* `updated_to` *(str)*: Fecha de referencia en la BD (`YYYY-MM-DD`).
* `format` *(str, opcional)*: Formato de la fecha (por defecto: `'%Y-%m-%d'`).

---

### 📤 Entregable / Valor de Retorno (`list[dict]` o `False`)

* **En caso de archivos nuevos válidos:** Lista de diccionarios enriquecida con la clave `"updated_to"` en formato string `YYYY-MM-DD`.
  ```python
  [
      {
          "tmp_path": "/mnt/datos1/downloaded_files/tmp/archivo_2026_02.xlsx",
          "download_url": "https://sitio.com/archivos/archivo_2026_02.xlsx",
          "updated_to": "2026-02-15"  # <--- Fecha interna extraída del contenido
      },
      {
          "tmp_path": "/mnt/datos1/downloaded_files/tmp/archivo_2026_03.xlsx",
          "download_url": "https://sitio.com/archivos/archivo_2026_03.xlsx",
          "updated_to": "2026-03-15"
      }
  ]
  ```

* **Si el archivo descargado era un ZIP:** `compare_files` descomprime el archivo interior (ej. Excel), actualiza `tmp_path` apuntando al archivo extraído y añade la clave `zip_path`:
  ```python
  [
      {
          "tmp_path": "/mnt/datos1/downloaded_files/tmp/extraido.xlsx",
          "download_url": "https://sitio.com/archivos/pack.zip",
          "zip_path": "/mnt/datos1/downloaded_files/tmp/original.zip",
          "updated_to": "2026-02-15"
      }
  ]
  ```

* **Si NO hay archivos nuevos o ante cualquier Error:** 👉 **DEBE RETORNAR `False`** (🚫 *nunca retornar lista vacía `[]`*).

---

### 🚨 Reglas Críticas para `compare_files`:

1. **Retorno Estricto V2:**
   * Si no hay archivos que superen la fecha de referencia:
     ```python
     return verified_files if verified_files else False
     ```

2. **Detección Robusta de Fechas en el Contenido:**
   * **Fechas en Español:** Si el documento tiene fechas en texto natural (ej. *"jueves, 20 de agosto de 2026"* o *"20 de agosto de 2026"*), usar expresiones regulares y convertir el mes en español a número usando `month_to_number()`.
   * **Fechas Estándar:** Detectar patrones `YYYY-MM-DD`, `DD/MM/YYYY`, o celdas de tipo `pd.Timestamp` / `datetime`.
   * **Nombre del archivo:** Si el nombre del archivo contiene la fecha (ej. `reporte_200826.xlsx`), usarlo como alternativa válida.
   * **Evitar fallos por columnas numéricas:** Si usas `pd.read_excel(..., header=None)`, las columnas son enteros (`0, 1...`), por lo que no debes asumir nombres de columnas tipo string.

---

## ✅ Criterios de Aceptación para Pull Requests
* [ ] Cumple estrictamente con **PEP 8**.
* [ ] Nombres de funciones, docstrings y comentarios en **inglés**.
* [ ] La clase se llama exactamente igual al código del robot (ej. `class D_BO_000000XXX(Download_Base):`).
* [ ] `get_file_url` retorna **todas las URLs** de publicaciones posteriores a `updated_to` (descarga histórica completa, sin descartar registros intermedios con `max()`).
* [ ] `compare_files` retorna **`False`** si no hay archivos nuevos o si ocurre una excepción.
* [ ] `compare_files` puebla correctamente la clave `"updated_to"` con la fecha interna de cada documento.
* [ ] El test unitario `models/download/tests/test_download_type_i.py` finaliza en **`OK`**.
