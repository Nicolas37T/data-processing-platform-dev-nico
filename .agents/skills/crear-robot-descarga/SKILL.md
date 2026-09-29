---
name: crear-robot-descarga
description: Guía completa para crear un robot de descarga (Web Scraping / API / Bulk) siguiendo los estándares oficiales de DATAX Platform.
---

# 📥 Skill: Crear Robot de Descarga

Esta skill guía la implementación de un robot de descarga (`robot.py` o `D_BO_...`) para interactuar con portales web, APIs gubernamentales/financieras o repositorios masivos.

---

## 🧭 Los 4 Tipos de Descarga y sus Plantillas de DAG

| Tipo | Métodos en el Robot | Plantilla DAG (`dags/templates/`) | Test Unitario | Descripción |
| :--- | :--- | :--- | :--- | :--- |
| **Tipo I** (`file_download_type_i`) | `get_file_url()`, `compare_files()` | `file_download_template.py` | `test_download_type_i.py` | Extrae URLs directas de descargas posteriores a `updated_to`. Airflow descarga el archivo. |
| **Tipo II** (`file_download_type_ii`) | `verify_download()`, `compare_files()` | `direct_download_template.py` | `test_download_type_ii.py` | Automatización Web (Playwright) con filtros/clicks que deposita archivos en `<path>/tmp`. |
| **Tipo III** (`file_download_type_iii`) | `check_new_data()` *(🚫 sin `compare_files`)* | `data_download_template.py` | `test_download_type_iii.py` | Consume API REST o genera dataset en disco (`.xlsx`/`.csv`) en `<path>/tmp`. Retorna `[{"tmp_path", "updated_to", "download_url"}]`. |
| **Tipo IV** (`file_download_type_iv`) | `get_data()` *(🚫 sin `compare_files`)* | `multi_file_download_template.py` | `test_download_type_iv.py` | Descarga masiva de repositorios completos a `<path>/tmp`. Archivos nombrados con prefijo `YYYY-MM-DD_...`. Retorna `str` con ruta de `tmp`. |

---

## 📌 Firmas y Métodos por Tipo de Descarga

### Tipo I: URLs Directas
```python
class D_BO_000000XXX(Download_Base):
    def get_file_url(self, main_url: str, updated_to: str, key_words: str = "", format: str = "%Y-%m-%d") -> list:
        """Retorna lista de URLs directas o tuplas con enlaces posteriores a updated_to."""
        pass

    def compare_files(self, file_path_1: str, file_path_2: str) -> bool:
        """Compara si dos archivos son idénticos."""
        pass
```

### Tipo II: Interacción Web / Formulario
```python
class D_BO_000000XXX(Download_Base):
    def verify_download(self, main_url: str, updated_to: str, path: str, key_words: str = "", format: str = "%Y-%m-%d") -> list:
        """Limpia/recrea <path>/tmp, interactúa con la web y descarga archivos. Retorna [{'tmp_path': ..., 'download_url': ...}]."""
        pass

    def compare_files(self, files_paths: list, updated_to: str, format: str = "%Y-%m-%d"):
        """Inspecciona archivos, extrae fecha real ('updated_to') y retorna lista filtrada o False si no hay novedades."""
        pass
```

### Tipo III: API REST / Spiders
```python
class D_BO_000000XXX(Download_Base):
    def check_new_data(self, main_url: str, updated_to: str, path: str, key_words: str = "", format: str = "%Y-%m-%d") -> list:
        """Limpia/recrea <path>/tmp, consulta API, construye archivos en tmp y retorna [{'tmp_path', 'updated_to', 'download_url'}]."""
        pass
```

### Tipo IV: Descarga Masiva (Bulk)
```python
class D_BO_000000XXX(Download_Base):
    def get_data(self, main_url: str, path: str, updated_to: str = None, format: str = "%Y-%m-%d") -> str:
        """Limpia/recrea <path>/tmp, descarga archivos nombrados 'YYYY-MM-DD_...' y retorna la ruta absoluta de tmp."""
        pass
```

---

## 🧹 Regla Crítica de Limpieza de Directorio Temporal (`tmp`)
Para los tipos II, III y IV, la función principal DEBE limpiar y recrear el directorio de trabajo al inicio:
```python
tmp_dir = os.path.join(path, "tmp")
if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)
os.makedirs(tmp_dir, exist_ok=True)
```

---

## 🧪 Pruebas Unitarias
Ejecutar el test correspondiente según el tipo:
```bash
python -m unittest models/download/tests/test_download_type_i.py
python -m unittest models/download/tests/test_download_type_ii.py
python -m unittest models/download/tests/test_download_type_iii.py
python -m unittest models/download/tests/test_download_type_iv.py
```
