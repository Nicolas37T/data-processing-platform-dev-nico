# 🚀 Protocolo Express: Creación de Robots de Descarga en DATAX

Este documento define el procedimiento exacto, directo y sin rodeos cuando indicas:
> *"Hola, quiero crear la descarga para [CÓDIGO_REPORTE]"*

---

## ⚡ Filosofía de Ejecución Ultra-Rápida
1. **Regla de Oro de Métodos Obligatorios**:
   - `get_file_url(self, specific_url, navigation_path, download_path, user_key=None) -> list`
   - `compare_files(self, file_path_1, file_path_2) -> bool`
   - `verify_url(self, url) -> bool`
2. **Descargas Seguras**:
   - Creación de carpetas con `from download_tools import createDirectoryStruct`.
   - Headers simulados de navegador para evitar bloqueos HTTP 403.
   - Retornar lista de rutas absolutas de archivos descargados: `[downloaded_file_path]`.
3. **Comparación de Archivos (`compare_files`)**:
   - Retorna `True` si son idénticos (no hay cambios).
   - Retorna `False` si el archivo nuevo tiene cambios respecto al anterior.

---

## 📋 Flujo Automatizado en 3 Pasos

### Paso 1: Generación Directa de `robot.py`
El asistente crea directamente la clase `Robot` con los 3 métodos implementados para descargar vía `requests`, API o Web Scraping según la fuente.

### Paso 2: Validación Local Inmediata
Comando de validación:
```bash
python validate_robot.py --type download --url "URL_ORIGEN"
```

### Paso 3: Publicación en Git
```bash
git add models/download/D_<PAIS>_<ID_BASE>/
git commit -m "feat(download): implement robot <CODIGO_REPORTE>"
git push origin <tu_rama>
```
