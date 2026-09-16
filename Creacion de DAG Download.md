# 📥 Manual Definitivo: Creación e Implementación de un DAG de Descarga (Plataforma V2)

Este manual documenta el **flujo de trabajo completo para robots de Descarga (`D_...`)** en la **Plataforma V2** (Airflow 3, PostgreSQL 17, servidor `10.0.0.16`), con los estándares oficiales de código, base de datos, pruebas y despliegue.

---

## **Paso 1: Crear la incidencia en Jira**

Crea una nueva incidencia (ticket) del tipo **`download request flow`** con los campos obligatorios:

- **Nombre del soporte / Institución:** (ej. *Boletín de Precios Avícolas - ADASZ*).
- **Código de descarga (`download code`):** Identificador único del robot (ej. `D_BO_000000462`).
- **URL principal (`main_url`):** Enlace web de donde se extraen o descargan los archivos.
- **Frecuencia de publicación:** Diario, semanal, mensual, etc.
- **Tipo de descarga:** `file_download_type_i` (scraping web con Playwright), `data_download` (API), `direct_download` (enlace directo), etc.

---

## **Paso 2: Mover la incidencia a "En curso"**

Al cambiar el estado del ticket a **"En curso"** (*In Progress*), la automatización de Jira:
1. Crea automáticamente la rama en Git (ej. `cristhian/D_BO_000000462`).
2. Registra la fila del soporte en la tabla **`file`** de la base de datos `platform_db`.
3. Pre-crea la estructura base de carpetas en `models/download/`.

---

## **Paso 3: Obtener la rama localmente**

En tu terminal local de desarrollo:

```bash
git fetch origin
git checkout cristhian/D_BO_000000462
git pull origin cristhian/D_BO_000000462
```

Verás creada la carpeta del modelo en:
`models/download/D_BO_000000462/D_BO_000000462.py`

---

## **Paso 4: Estandarizar e integrar el código del robot**

Edita `models/download/D_BO_000000462/D_BO_000000462.py` aplicando los estándares de la V2:

### 📐 Reglas de Oro para Robots de Descarga:
1. **Nombre de la clase y archivo:** Debe llamarse exactamente igual al ID del robot:
   ```python
   class D_BO_000000462(Download_Base):
   ```
2. **Herencia e Imports:**
   ```python
   import traceback
   from models.download.Download_Base import Download_Base
   from models.download.tools.download_tools import format_date, text_extract  # helpers según aplique
   ```
3. **Estructura Estricta de SOLO 2 métodos:**
   - **`get_file_url(self, main_url, updated_to, ...)`**:
     - Localiza los enlaces en la web.
     - **Debe retornar una lista de URLs en string**: `list[str]`.
     - ⚠️ **URLs siempre absolutas**: Usa siempre `from urllib.parse import urljoin` para concatenar (`urljoin(base_url, href)`). URLs relativas (ej. `/sites/...`) provocan fallo inmediato en las pruebas unitarias (`is_valid_url`) y en la descarga.
     - ⚠️ **Cuidado con selectores XPath en Playwright**: Nunca uses `row.query_selector('//a')` dentro de una fila, pues en XPath `//` evalúa desde la raíz de todo el documento. Usa selectores CSS como `row.query_selector('a')` o XPath relativo `.//a`.
   - **`compare_files(self, files_paths, updated_to, format='%Y-%m-%d')`**:
     - Extrae la fecha del archivo descargado y compara contra `updated_to`.
     - ⚠️ **Extracción de fecha resiliente**: Evita `.split('.')` o delimitadores fijos. Usa expresiones regulares por grupos como `r"(\d{1,2})\D+(\d{1,2})\D+(\d{4})"` para capturar `(día, mes, año)` sin importar si el archivo usa guiones `-`, barras `/` o puntos `.`.
     - Si hay archivo nuevo, **debe retornar una lista de diccionarios** con estas 3 claves exactas:
       ```python
       return [{
           'tmp_path': file_path,
           'updated_to': fecha_del_documento,
           'download_url': url_origen
       }]
       ```
     - Si NO hay archivos nuevos o el archivo no es más reciente que `updated_to`:
       👉 **DEBE RETORNAR `False`** (🚫 *nunca retornar lista vacía `[]`*).
4. **Archivo `__init__.py` obligatorio:**
   Crea siempre un `__init__.py` vacío dentro de `models/download/<CODIGO>/` para asegurar la importación de módulos en cualquier entorno.

---

## **Paso 5: Configurar la base de datos (`platform_db` ➔ tabla `file`)**

Conéctate a `platform_db` (en `10.0.0.16:5434`) y verifica el registro en la tabla **`file`**:

```sql
SELECT id_file, code, main_url, download_type, schedule_interval, 
       publication_frequency, state, updated_to, last_file_path 
FROM file 
WHERE code = 'D_BO_000000462';
```

### Campos clave:
- **`state`**: `'active'`
- **`main_url`**: La URL web donde están los documentos.
- **`download_type`**: `'file_download_type_i()'` (o el tipo correspondiente).
- **`schedule_interval`**: Expresión Cron (ej. `'0 10 * * 1-5'`).
- **`updated_to`**: Para pruebas iniciales, pon una fecha anterior (ej. `'2024-05-31'` o `'1900-01-01'`) para asegurar que detecte el archivo como nuevo.

---

## **Paso 6: Configurar y ejecutar el test unitario**

Abre el archivo de test correspondiente a tu tipo de descarga:
`models/download/tests/test_download_type_i.py`

1. Configura el código del robot y fecha de referencia:
   ```python
   CODE_ROBOT = 'D_BO_000000462'
   UPDATED_TO = '2024-05-31'
   ```
2. Asegúrate de que la conexión en `setUp()` apunte a `10.0.0.16:5434`:
   ```python
   _host = "10.0.0.16"
   _port = "5434"
   _user = "postgres"
   _password = "datax"
   platform_engine = create_engine(f"postgresql+psycopg2://{_user}:{_password}@{_host}:{_port}/platform_db")
   ```
3. Ejecuta el test dentro del contenedor:
   ```bash
   docker exec -it data-processing-platform-dev-airflow-worker-1 python -m unittest models/download/tests/test_download_type_i.py
   ```
   > Debe terminar en **`OK`** tras descargar y validar las fechas.

---

## **Paso 7: Generar el DAG en el proyecto**

Usa el generador unificado por consola de la Plataforma V2:

```bash
docker exec -it data-processing-platform-dev-airflow-worker-1 python include/main-generate.py
```

1. Selecciona la opción **`1. Download`**.
2. Selecciona la opción **`1. Enter robot code(s)`**.
3. Ingresa el código: **`D_BO_000000462`**.
4. Se generará automáticamente el wrapper en `dags/download/D_BO_000000462.py`.

---

## **Paso 8: Infraestructura y Permisos de Directorios**

Asegúrate de que el volumen de descargas esté montado en `docker-compose.yaml` y tenga permisos totales en el host:

```bash
sudo chmod -R 777 /mnt/datos1/downloaded_files
```

---

## **Paso 9: Probar el DAG en Airflow**

A diferencia de los DAGs de conversión, **el DAG de descarga SÍ se puede ejecutar directamente**:

```bash
docker exec data-processing-platform-dev-airflow-worker-1 airflow dags trigger D_BO_000000462
```

*(O desde la UI web de Airflow dándole al botón Play).*

---

## **Paso 10: Validar la Ejecución Completa**

Una vez que el DAG termine en **Verde (Success)**, valida 4 puntos:

1. **Archivo físico descargado en el servidor:**
   ```bash
   find /mnt/datos1/downloaded_files/BO/D_BO_000000462 -type f
   ```
   *(Debe aparecer el archivo dentro de su carpeta `YYYY/YYYY-MM/YYYY-MM-DD_nombre.ext`).*

2. **Registro de auditoría en la tabla `download`:**
   ```sql
   SELECT id_download, id_file, downloaded_to, download_hash, state, path 
   FROM download 
   WHERE id_file = (SELECT id_file FROM file WHERE code = 'D_BO_000000462')
   ORDER BY id_download DESC LIMIT 1;
   ```

3. **Actualización de la tabla `file`:**
   ```sql
   SELECT code, updated_to, last_file_path FROM file WHERE code = 'D_BO_000000462';
   ```
   *(El campo `updated_to` debe tener la fecha del documento descargado).*

4. **Encadenamiento automático a Conversión:**
   En la UI de Airflow, la última tarea `trigger_dags` disparará automáticamente el DAG de conversión correspondiente (`C_BO_...`) pasándole el `id_download` y el `file` recién descargados.

---

## **Paso 11: Commit, Push y Merge**

```bash
git add models/download/D_BO_000000462/
git commit -m "feat(download): implement and validate robot D_BO_000000462"
git push origin cristhian/D_BO_000000462
```

1. Crea el **Pull Request / Merge Request** hacia `main`.
2. Realiza el **Merge**.
3. Pasa la incidencia en Jira a **"Finalizado" / "Done"**.

---

¡Con este manual tienes la guía definitiva paso a paso para todos los robots de descarga! 🚀