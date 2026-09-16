---
name: crear-robot-descarga
description: Guía completa para crear un robot de descarga (Web Scraping / API) siguiendo los estándares oficiales de DATAX Platform.
---

# 📥 Skill: Crear Robot de Descarga

Esta skill guía la implementación de un robot de descarga (`robot.py`) que interactúa con portales web o APIs gubernamentales/financieras para obtener archivos fuente.

---

## 📌 Métodos Obligatorios de la Clase Robot
```python
class Robot:
    def get_file_url(self, specific_url, navigation_path, download_path, user_key=None) -> list:
        """Navega y descarga el archivo, retornando lista de rutas de archivos descargados."""
        pass

    def compare_files(self, file_path_1, file_path_2) -> bool:
        """Compara si dos archivos son idénticos (ej. hash SHA256)."""
        pass

    def verify_url(self, url) -> bool:
        """Verifica la accesibilidad del portal objetivo."""
        pass
```

---

## 🛡️ Herramientas Locales
Importar utilidades desde `download_tools.py`:
```python
from download_tools import createDirectoryStruct
```

## 🧪 Pruebas
Ejecutar la prueba correspondiente según el tipo de descarga:
```bash
python -m unittest test_download_type_i.py
# o
python -m unittest test_download_type_ii.py
```
