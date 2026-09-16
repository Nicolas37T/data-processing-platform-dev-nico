---
name: validar-robot
description: Ejecuta la suite de verificación automatizada sobre robot.py y diagnostica fallas contra los estándares oficiales de DATAX.
---

# 🧪 Skill: Validar Robot (DATAX)

Usa esta skill para comprobar si el robot en `robot.py` cumple al 100% las reglas de arquitectura y calidad antes de subirlo a Git.

---

## 🔍 Verificaciones que Realiza
1. **Existencia y Sintaxis**:
   - Comprueba la compilación limpia con `py_compile`.
2. **Estructura de la Clase Robot**:
   - **Regla Estricta de 2 Métodos**: Verifica que la clase tenga ÚNICAMENTE `extraction()` y `validate_data_results()`.
   - **Prohibición de `__init__`**: Comprueba que no exista constructor en la clase.
   - **Prohibición de métodos `self` auxiliares**: Funciones de soporte deben estar anidadas dentro de `extraction()` o a nivel de módulo.
3. **Control de Fechas**:
   - Detecta si hay fechas estáticas en duro en declaraciones `return`.
4. **Pruebas Unitarias Oficiales**:
   - Ejecuta `test_conversion.py` (o `test_download_type_*.py`).
5. **Reconciliación Matemática**:
   - Ejecuta `validate_data_results(dataframe)` sobre los datos extraídos y comprueba que retorne `False` (éxito).

---

## 💻 Comando de Ejecución
```bash
python validate_robot.py
```
O especificando el tipo y archivo:
```bash
python validate_robot.py --type conversion --file "<archivo_muestra>"
```
