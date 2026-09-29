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

doc_md = """## 🔄 DAG Conversión: C_BO_000000051

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **ASFI** (Autoridad de Supervisión del Sistema Financiero) |
| **📄 Reporte(s)** | Entidades de Arrendamiento Financiero (D_BO_000000051_01) |
| **🔑 Palabras Clave** | entidades arrendamiento |
| **📍 Ubicación** | 1 |
"""

dag = DAG('C_BO_000000051',
        default_args=default_args,        
        tags= ['ASFI', 'Conversion', 'entidades arrendamiento'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db', id_dag='C_BO_000000051')
