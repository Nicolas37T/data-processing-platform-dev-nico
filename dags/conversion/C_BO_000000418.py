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

doc_md = """## 🔄 DAG Conversión: C_BO_000000418

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **BCB** (Banco Central de Bolivia) |
| **📊 Dataset(s)** | `S_BOBCB_22_000723` |
| **📝 Nombre Dataset** | Tasas Interbancarias |
| **📄 Reporte(s)** | Tasas Interbancarias |
| **📅 Última Conversión** | **2026-08-30** |
| **🔑 Palabras Clave** | tasas interbancarias |
| **📍 Ubicación** | 1 |
| **💾 Ruta Almacén** | `//10.0.0.16/data_process/BO/D_BO_000000418/` |
"""

dag = DAG('C_BO_000000418',
        #schedule= schedule-to-replace,
        default_args=default_args,        
        tags= ['BCB', 'S_BOBCB_22_000723', 'Conversion', '2026-08-30', 'tasas interbancarias'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='C_BO_000000418')
