---
name: subir-al-git
description: Guía y asiste al desarrollador en el flujo de publicación en Git, renombrando la rama asignada de origin y subiendo el robot a GitHub con enlace a Pull Request.
---

# 🚀 Skill: Subir Robot al Repositorio Git

Esta skill guía y automatiza el proceso de publicación del robot desarrollado en `data-processing-modules` cuando todas las pruebas (`validate_robot.py` y `test_conversion.py`) hayan pasado con éxito.

---

## 📌 Contexto del Flujo de Ramas en DATAX
1. En GitHub ya existe una rama remota creada para el reporte asignado con el formato `<CODIGO_REPORTE>` (ejemplo: `origin/D_BO_000000270_01`).
2. El estándar de DATAX exige que la rama de trabajo de cada desarrollador lleve su nombre como prefijo:
   `<nombre_desarrollador>/<CODIGO_REPORTE>` (ejemplo: `nicolas/D_BO_000000270_01`, `cristhian/D_BO_000000418_02`, `andresrevollo/D_BO_000000485_01`).
3. Por lo tanto, el flujo consiste en **renombrar la rama de origen** y publicar únicamente los archivos del robot.

---

## 🛠️ Procedimiento Paso a Paso

### Paso 1: Confirmar Nombre y Código de Reporte
Confirmar con el desarrollador:
- Nombre o identificador personal (ej. `nicolas`, `cristhian`, `andres`).
- Código del reporte asignado (ej. `D_BO_000000270_01`).

### Paso 2: Crear y Cambiar a la Rama Renombrada
Si aún no estás en la rama renombrada, crearla a partir de la rama remota base:
```bash
git fetch origin
git checkout -b <nombre>/<CODIGO_REPORTE> origin/<CODIGO_REPORTE>
```

### Paso 3: Verificar Estado y Agregar Archivos
Solo agregar los archivos necesarios para el robot (evitar datos o archivos temporales no requeridos):
```bash
git status
git add robot.py test_conversion.py
```

### Paso 4: Realizar el Commit
Hacer commit con mensaje estandarizado:
```bash
git commit -m "feat(conversion): implement robot for <CODIGO_REPORTE>"
```

### Paso 5: Publicar la Rama en GitHub
Hacer push de la nueva rama configurando el upstream (`-u`):
```bash
git push -u origin <nombre>/<CODIGO_REPORTE>
```

### Paso 6: Eliminar la Rama Remota Anterior (Completar Renombre)
Una vez subida la nueva rama, eliminar la rama genérica de `origin`:
```bash
git push origin --delete <CODIGO_REPORTE>
```

### Paso 7: Generar Enlace de Pull Request
Mostrar al desarrollador el enlace directo para abrir su Pull Request hacia `main`:
`https://github.com/datax-platform/data-processing-modules/pull/new/<nombre>/<CODIGO_REPORTE>`
