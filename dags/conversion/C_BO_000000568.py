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

doc_md = """## 🔄 DAG Conversión: C_BO_000000568

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **BCB** (Banco Central de Bolivia) |
| **📊 Dataset(s)** | `S_BOBCB_11_000321`, `S_BOBCB_11_000480` |
| **📝 Nombre Reporte** | Tipos de Cambio Dólar Pactados con Clientes |
| **💾 Ruta Almacén** | `//10.0.0.16/data_process/BO/D_BO_000000568/` |
"""

dag = DAG('C_BO_000000568',
        default_args=default_args,        
        tags= ['BCB', 'Conversion', 'Tipos Cambio'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db', id_dag='C_BO_000000568')
