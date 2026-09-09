# 🛠️ Especificaciones de Desarrollo: Descarga Tipo III (`file_download_type_iii`)

> 📌 **Reglas Generales de la Plataforma (V2):**
> * Código bajo estándares estrictos **PEP 8**.
> * Comentarios y `docstrings` estrictamente en **inglés**.
> * Clase nombrada idéntica al código del robot heredando de `Download_Base`:
>   ```python
>   class D_BO_000000XXX(Download_Base):
>   ```
> * **Atención:** Los robots Tipo III **no requieren** la función `compare_files()`, ya que `check_new_data()` consulta directamente la fuente (API o web), construye el archivo en disco y calcula la clave `"updated_to"`.

---

## 1. Función: `check_new_data`

### 📌 Descripción General
Obtiene datos directamente desde una API REST, scraping web (Playwright) o spiders (Scrapy). Evalúa si la fecha del portal/API supera a `updated_to`. Si hay datos nuevos, construye el dataset, lo guarda como Excel (`.xlsx`) o CSV (`.csv`) en la carpeta `<path>/tmp` y retorna el listado de archivos generados con sus respectivas fechas internas.

> 🧹 **Gestión de Limpieza:** Al iniciar la ejecución, la carpeta `<path>/tmp` debe eliminarse (si existe) y recrearse para garantizar un entorno de trabajo limpio.

---

### 📥 Parámetros de Entrada
* `main_url` *(str)*: URL base de la API, portal o servicio de datos.
* `updated_to` *(str)*: Fecha de la última actualización en la BD (`YYYY-MM-DD`).
* `path` *(str)*: Directorio base donde se creará la carpeta `tmp` para depositar los archivos generados.
* `key_words` *(str, opcional)*: Nombre base o identificador utilizado para nombrar el archivo generado (ej. indicador o variable).
* `format` *(str, opcional)*: Formato de la fecha `updated_to` (por defecto: `'%Y-%m-%d'`).

---

### 📤 Entregable / Valor de Retorno (`list[dict]`)

* **En caso de éxito / nuevos datos generados:** Lista de diccionarios donde cada elemento incluye la ruta del archivo generado en `tmp`, la fecha interna calculada y la URL de origen:
  ```python
  [
      {
          "tmp_path": "/mnt/datos1/downloaded_files/tmp/indicador_2026_08.xlsx",
          "updated_to": "2026-08-13",  # Fecha detectada en la API/Portal (YYYY-MM-DD)
          "download_url": "https://api.bcrp.gob.pe/datos"  # URL o "-" como placeholder
      }
  ]
  ```

* **Si no hay datos nuevos / Error / Excepción:** Lista vacía `[]`.

---

### 🚨 Reglas Críticas para `check_new_data`:

1. **Descarga Histórica Completa:**
   * Si la API o servicio permite consultar rangos de fechas (ej. desde `updated_to` hasta hoy), se deben generar los archivos correspondientes a **todos** los períodos nuevos pendientes, sin omitir datos intermedios.

2. **Manejo de Fechas:**
   * Extraer la fecha real que reporta la API o el portal.
   * Si no es posible extraer una fecha explícita desde la API, se puede utilizar la fecha actual del sistema (`pd.Timestamp.now().strftime(format)`) en el campo `"updated_to"`.

3. **Estructura Estricta de Claves:**
   * Cada diccionario devuelto en la lista debe contener exactamente las 3 claves: `{"tmp_path", "updated_to", "download_url"}`.

---

## ✅ Criterios de Aceptación para Pull Requests
* [ ] Cumple estrictamente con **PEP 8**.
* [ ] Documentación, nombres de variables y comentarios en **inglés**.
* [ ] Recrea la carpeta `<path>/tmp` al iniciar la ejecución.
* [ ] Retorna diccionarios con las 3 claves obligatorias: `tmp_path`, `updated_to`, `download_url`.
* [ ] El archivo generado existe físicamente en disco y es legible.
* [ ] El test unitario `models/download/tests/test_download_type_iii.py` finaliza en **`OK`**.
