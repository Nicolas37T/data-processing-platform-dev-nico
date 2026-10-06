---
name: indexar-dataset-dssm
description: Indexa, perfila y certifica automáticamente nuevos datasets y cubos estadísticos de DATAX al modelo DSSM V0.2.2 (OpenAI Data Partnership).
---

# 🤖 Skill: Indexar Dataset al Modelo Semántico DSSM

Esta skill automatiza el onboarding completo de nuevos reportes y cubos de DATAX al **Statistical Semantic Model (DSSM V0.2.2)**, dejándolos listos para ser consumidos por el Catálogo 3D, el Chat con IA y la API de OpenAI.

---

## ⚡ Ejecución Rápida en 1 Comando

Para incorporar un cubo y su dataset, ejecuta:

```bash
python C:\Users\DATAX\Documents\Nicolas\datax-semantic-layer\backend\scripts\onboard_dataset.py --cube <CODIGO_CUBO> --dataset <CODIGO_DATASET>
```

**Ejemplo real (Precios Internacionales del Cacao):**
```bash
python C:\Users\DATAX\Documents\Nicolas\datax-semantic-layer\backend\scripts\onboard_dataset.py --cube SPIM_13001_IDPCB --dataset D_BO_000000043_01
```

---

## 🔄 Qué hace la Skill Automáticamente:

1. **Inspección en `platform_db`:**
   - Lee el nombre oficial, fuente originaria (`FDTA-Valles`, `INE`, `ADA`, `ASFI`), frecuencia de publicación y esquema/tabla física.
2. **Auditoría y Perfilado en `DATA_DB_BO`:**
   - Verifica en PostgreSQL el conteo total de filas (`COUNT(*)`), rango temporal (`MIN(fecha)` a `MAX(fecha)`), valores nulos y unicidad de la coordenada de grano (`grain`).
3. **Generación de Catálogos Markdown:**
   - Crea automáticamente los archivos de documentación con diccionarios de datos en:
     `backend/catalog/<FUENTE>/<CUBO>/<DATASET>.md` y `<CUBO>.md`.
4. **Inyección en el Registro Semántico DSSM:**
   - Registra el dataset en [dssm_registry.py](file:///C:/Users/DATAX/Documents/Nicolas/datax-semantic-layer/backend/app/core/dssm_registry.py) con su firma de 4 ejes (`measure_kind`, `quantity_kind`, `temporal_behavior`, `aggregation_class`).
5. **Auditoría en Vivo (Paso 3 del DSSM):**
   - Ejecuta los 6 niveles de validación (V1 Estructural a V6 Gobernanza) y genera el certificado verde `STATUS: VALIDATED (6/6 Checks OK)`.

---

## 📋 Verificación en la Interfaz:
- El nuevo cubo aparece inmediatamente en la **Nube 3D del Catálogo**.
- En la ficha técnica se puede presionar **«Ejecutar Auditoría en Vivo (Paso 3)»** para auditar en tiempo real contra PostgreSQL.
- El Chat con IA ya puede responder preguntas sobre el nuevo dataset respetando sus reglas semánticas y mostrando su **Linaje y Provenance (Bloque E)**.
