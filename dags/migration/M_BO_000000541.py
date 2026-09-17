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

doc_md = """## 🚚 DAG Migración: M_BO_000000541

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **BCB** (Banco Central de Bolivia) |
| **📊 Dataset(s)** | `S_MUMUL_11_000684` |
| **📝 Nombre Dataset** | Tasas de Interes Diarios del Libor, Euribor y Prime |
| **📄 Sub-reporte(s)** | Tasas de Interes diarios SOFR |
| **🗄️ Tabla(s) Almacén** | `BCB;DATA_D_BO_000000541_01` |
| **📅 Última Migración** | **2026-08-31** |
"""

dag = DAG('M_BO_000000541',
        #schedule= schedule-to-replace,
        default_args=default_args,        
        tags= ['BCB', 'S_MUMUL_11_000684', 'Migration', '2026-08-31'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='M_BO_000000541')#ALL=True)
