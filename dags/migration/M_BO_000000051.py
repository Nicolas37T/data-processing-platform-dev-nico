import sys
import os
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/dags')
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.migration_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

doc_md = """## 🚚 DAG Migración: M_BO_000000051

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **ASFI** (Autoridad de Supervisión del Sistema Financiero) |
| **📄 Sub-reporte(s)** | Entidades de Arrendamiento Financiero (D_BO_000000051_01) |
| **🗄️ Tabla(s) Almacén** | `ASFI;DATA_D_BO_000000051_01` |
"""

dag = DAG('M_BO_000000051',
        default_args=default_args,        
        tags= ['ASFI', 'Migration'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db', id_dag='M_BO_000000051')
