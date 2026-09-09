import sys
import os
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/dags')
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.conversion_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

doc_md = """## 🔄 DAG Conversión: C_BO_000000462

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **ADA** (Asociación de Avicultores) |
| **📊 Dataset(s)** | `S_BOADA_11_000730, S_BOADA_11_000731` |
| **📝 Nombre Dataset** | Evolucion del Precio del Pollo - Santa Cruz / Precios de Insumos Alimentos para Pollo - Santa Cruz |
| **📄 Reporte(s)** | Precios Referenciales del Pollo / Precios Referenciales de Insumos |
| **📅 Última Conversión** | **2026-09-07** |
| **🔑 Palabras Clave** | Precios Referenciales del Pollo, precio |
| **📍 Ubicación** | 1 |
| **💾 Ruta Almacén** | `//10.0.0.16/data_process/BO/D_BO_000000462/` |
"""

dag = DAG('C_BO_000000462',
        #schedule= schedule-to-replace,
        default_args=default_args,        
        tags= ['ADA', 'S_BOADA_11_000730', 'S_BOADA_11_000731', 'Conversion', '2026-09-07', 'precio'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='C_BO_000000462')#ALL=True)
