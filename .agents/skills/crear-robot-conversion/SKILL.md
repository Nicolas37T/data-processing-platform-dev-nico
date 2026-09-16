---
name: crear-robot-conversion
description: Guía completa para crear un robot de conversión de datos (Excel/PDF) siguiendo los estándares oficiales de DATAX Platform.
---

# 🔄 Skill: Crear Robot de Conversión

Esta skill guía el desarrollo de un robot de conversión (`robot.py`) que transforma archivos de entrada (Excel o PDF) en un `DataFrame` vertical (*melted*) normalizado.

---

## Flujo de Trabajo en 5 Pasos

### Paso 1: Inspeccionar el Archivo Fuente
1. Identificar el nombre y extensión del archivo (ej. `2026-06-30_deuda interna.xlsx`).
2. Identificar la pestaña objetivo (en libros Excel) o página objetivo (en PDF).
3. Analizar la jerarquía visual con el esquema de colores:
   - **Naranja**: Total General (`nv1` para todas las filas).
   - **Celestes**: Sectores / Categorías mayores (`nv2`).
   - **Verdes**: Entidades o Subsectores (`nv3`).
   - **Amarillos**: Instrumentos / Hojas (`nv4`, `nv5`).

### Paso 2: Configurar las Fechas Dinámicas
- Extraer el año y mes de corte dinámicamente del nombre del archivo (`YYYY-MM-DD`).
- Resolver las fechas de cada columna/fila al último día del mes correspondiente (`calendar.monthrange`).
- NUNCA quemar fechas fijas estáticas en duro.

### Paso 3: Implementar `robot.py`
> [!IMPORTANT]
> **REGLA ESTRICTA DE 2 MÉTODOS**: La clase solo debe tener `extraction()` y `validate_data_results()`.
> No usar `__init__`. Anidar funciones auxiliares dentro de `extraction()`.

```python
import os
import re
import calendar
import openpyxl
import pandas as pd
from typing import Tuple

from conversion_tools import to_numeric_datax

try:
    from models.conversion import Conversion_Base
except ImportError:
    Conversion_Base = object


class Robot(Conversion_Base):
    def extraction(self, file_path, key_words="", template_path="", page_number=1, format="%Y-%m-%d") -> Tuple[dict, pd.DataFrame]:
        # 1. Resolver fechas y hoja objetivo
        # 2. Iterar filas y mapear nv1..nvN
        # 3. Limpiar valores numericos con to_numeric_datax
        # 4. Retornar metadata_dict y df_data
        pass

    def validate_data_results(self, dataframe: pd.DataFrame, decimal_separator: str = ",", TOLERANCE: float = 6.0) -> bool:
        # Reconciliar sumas por fecha:
        # Suma de componentes == Total General
        return False
```

### Paso 4: Validar y Ejecutar Pruebas
1. Configurar `test_conversion.py` con `FILE_PATH`, `KEY_WORDS` y `PAGE_NUMBER`.
2. Ejecutar la suite completa:
   ```bash
   python validate_robot.py --type conversion --file "<archivo_muestra>"
   python -m unittest test_conversion.py
   ```

### Paso 5: Publicar en Git
- Activar la skill `subir-al-git` para publicar la rama en GitHub.
