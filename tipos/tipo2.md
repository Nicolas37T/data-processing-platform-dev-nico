# 🛠️ Especificaciones de Desarrollo: Descarga Tipo II (`file_download_type_ii`)

> 📌 **Reglas Generales de la Plataforma (V2):**
> * Código bajo estándares estrictos **PEP 8**.
> * Comentarios y `docstrings` estrictamente en **inglés**.
> * Clase nombrada idéntica al código del robot heredando de `Download_Base`:
>   ```python
>   class D_BO_000000XXX(Download_Base):
>   ```
> * Estructura estricta de **SOLO 2 métodos**: `verify_download` y `compare_files`.

---

## 1. Función: `verify_download`

### 📌 Descripción General
Navega el portal web (generalmente usando Playwright), interactúa con los controles/filtros del sitio (ej. selectores de año, departamento, rangos de fechas o categorías), descarga **todos los archivos** correspondientes a fechas posteriores a `updated_to` y los deposita directamente en el directorio temporal `<path>/tmp`.

> 🧹 **Gestión de Limpieza:** Al iniciar la función, la carpeta `<path>/tmp` debe eliminarse (si existe) y recrearse para garantizar un entorno limpio y evitar acumulación de descargas residuales.

---

### 📥 Parámetros de Entrada
* `main_url` *(str)*: URL principal del portal a navegar.
* `updated_to` *(str)*: Fecha de referencia en la BD (`YYYY-MM-DD`). Se descargan publicaciones posteriores.
* `path` *(str)*: Directorio base donde se creará la carpeta `tmp` con las descargas.
* `format` *(str, opcional)*: Formato de la fecha `updated_to` (por defecto: `'%Y-%m-%d'`).

---

### 📤 Entregable / Valor de Retorno (`list[dict]`)

* **En caso de éxito / descargas completadas:** Lista de diccionarios con la ruta local absoluta de cada archivo descargado y su URL de origen.
  ```python
  [
      {
          "tmp_path": "/mnt/datos1/downloaded_files/tmp/archivo_2026_01.xlsx",
          "download_url": "https://portal.com/descarga/123"  # O "-" si es descarga directa por evento
      },
      {
          "tmp_path": "/mnt/datos1/downloaded_files/tmp/archivo_2026_02.xlsx",
          "download_url": "https://portal.com/descarga/124"
      }
  ]
  ```

* **Si no hay archivos nuevos / Error / Excepción:** Lista vacía `[]`.

---

### 🚨 Reglas Críticas para `verify_download`:

1. **Descarga Histórica Completa (🚫 Prohibido `max()`):**
   * El robot debe iterar y descargar **TODOS los archivos pendientes** desde `updated_to` hasta la fecha actual.
   * Si existen múltiples años o meses con publicaciones nuevas, el robot debe interactuar con los selectores de la página para descargar cada uno de ellos.
   * ❌ **Error típico:** Descargar únicamente el archivo más reciente ignorando los períodos intermedios.

2. **Gestión de Directorio Temporal (`tmp`):**
   ```python
   tmp_dir = os.path.join(path, "tmp")
   if os.path.exists(tmp_dir):
       shutil.rmtree(tmp_dir)
   os.makedirs(tmp_dir, exist_ok=True)
   ```

---

## 2. Función: `compare_files`

### 📌 Descripción General
Recibe la lista de diccionarios retornada por `verify_download`, inspecciona el contenido interno de cada archivo en `tmp_path` (PDF, Excel, ZIP) para extraer la **fecha real del reporte**, y filtra aquellos cuya fecha interna sea estrictamente posterior a `updated_to`.

---

### 📥 Parámetros de Entrada
* `files_paths` *(list[dict])*: Lista de diccionarios con las rutas temporales.
  * *Estructura obligatoria por elemento:*
    ```python
    {
        "tmp_path": "/mnt/datos1/downloaded_files/tmp/archivo.xlsx",
        "download_url": "https://..."
    }
    ```
* `updated_to` *(str)*: Fecha de referencia en la BD (`YYYY-MM-DD`).
* `format` *(str, opcional)*: Formato de la fecha (por defecto: `'%Y-%m-%d'`).

---

### 📤 Entregable / Valor de Retorno (`list[dict]` o `False`)

* **En caso de archivos válidos:** Lista de diccionarios enriquecida con la clave `"updated_to"` que contiene la fecha interna real extraída del contenido (`YYYY-MM-DD`).
  ```python
  [
      {
          "tmp_path": "/mnt/datos1/downloaded_files/tmp/archivo_2026_02.xlsx",
          "download_url": "https://portal.com/descarga/124",
          "updated_to": "2026-02-15"  # <--- Fecha interna real del reporte
      }
  ]
  ```

* **Si el archivo descargado era un ZIP:** `compare_files` extrae el archivo interior (ej. Excel), actualiza `tmp_path` apuntando al archivo extraído y agrega `zip_path`:
  ```python
  [
      {
          "tmp_path": "/mnt/datos1/downloaded_files/tmp/extraido.xlsx",
          "download_url": "https://portal.com/descarga/zip",
          "zip_path": "/mnt/datos1/downloaded_files/tmp/original.zip",
          "updated_to": "2026-02-15"
      }
  ]
  ```

* **Si NO hay archivos nuevos o ante cualquier Error:** 👉 **DEBE RETORNAR `False`** (🚫 *nunca retornar lista vacía `[]`*).
  ```python
  return verified_files if verified_files else False
  ```

---

## ✅ Criterios de Aceptación para Pull Requests
* [ ] Cumple estrictamente con el estándar **PEP 8**.
* [ ] Nombres de métodos, docstrings y comentarios en **inglés**.
* [ ] Recrea limpiamente la carpeta `<path>/tmp` al iniciar `verify_download`.
* [ ] Descarga **todos los archivos** históricos pendientes que superen `updated_to`.
* [ ] `compare_files` retorna **`False`** si ningún archivo supera `updated_to` o ante excepciones.
* [ ] `compare_files` incluye la clave `"updated_to"` en formato `YYYY-MM-DD`.
* [ ] El test unitario `models/download/tests/test_download_type_ii.py` finaliza en **`OK`**.
