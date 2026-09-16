# 🚀 Protocolo Express: Creación de Robots de Conversión en DATAX

Este documento define el procedimiento exacto, directo y sin rodeos cuando indicas:
> *"Hola, quiero crear la conversión para [CÓDIGO_REPORTE]"*

---

## ⚡ Filosofía de Ejecución Ultra-Rápida
1. **Regla de Oro Estricta de 2 Métodos**:
   - `extraction(self, file_path, key_words, template_path="", page_number=1, format="%Y-%m-%d")`
   - `validate_data_results(self, dataframe, decimal_separator=",", TOLERANCE=6.0)`
   - ❌ **PROHIBIDO**: `__init__`, métodos con `self._auxiliar()`. Toda función extra va **anidada en `extraction()`** o a nivel de módulo.
2. **Jerarquía Visual de Niveles (`nv1..nvN`)**:
   - **`nv1` (Naranja)**: Total General / Título Raíz del reporte.
   - **`nv2` (Celeste)**: Sectores o Agrupadores mayores (`None` en fila total general).
   - **`nv3` (Verde)**: Entidades, subsectores o sub-agrupadores.
   - **`nv4` / `nv5` (Amarillo)**: Instrumentos y tipos específicos.
3. **Contrato de Salida**:
   - `metadata_dict`: `{"file_name": ..., "titles": [...], "page_number": int}`
   - `df_melted`: `nv1..nvN`, penúltima columna `fecha` (`YYYY-MM-DD`), última columna `valor` (numérico estricto con `to_numeric_datax`).
4. **Validación Numérica (`validate_data_results`)**:
   - `return False`: Datos consistentes y válidos.
   - `return True`: Discrepancia o error numérico.

---

## 📋 Flujo Automatizado en 3 Pasos

### Paso 1: Generación Directa de `robot.py`
El asistente crea directamente el código en `models/conversion/C_<PAIS>_<ID_BASE>/D_<PAIS>_<ID_REPORTE>.py` (o en la rama de trabajo `robot.py`) con la extracción y validación completas.

### Paso 2: Validación Local Inmediata
Comandos listos para correr:
```bash
python validate_robot.py --type conversion --file "ruta/al/archivo_muestra"
python -m unittest test_conversion.py
```

### Paso 3: Publicación y PR
```bash
git add models/conversion/C_<PAIS>_<ID_BASE>/
git commit -m "feat(conversion): implement robot <CODIGO_REPORTE>"
git push origin <tu_rama>
```
