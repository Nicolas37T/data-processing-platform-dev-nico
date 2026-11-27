import sys
import os
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/dags')
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.file_download_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

doc_md = """## 📥 DAG Descarga: D_BO_000000103

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **BCB** (Banco Central de Bolivia) |
| **📊 Dataset(s)** | `SPIM_1050_ODLT` |
| **📝 Nombre Dataset** | Origen de la Liquidez Total |
| **📁 Archivo** | Origen de la liquidez Total |
| **⚙️ Tipo Descarga** | Tipo I (file_download_template) |
| **📅 Última Descarga** | **2026-08-31** |
| **⏱️ Frecuencia** | `22 13 * * 1,3` |
| **🧭 Ruta Web** | - |
| **🌐 Portal Web** | [Abrir portal ↗](https://www.bcb.gob.bo/?q=content/sector-monetario) |
"""

dag = DAG('D_BO_000000103',
        schedule= '22 13 * * 1,3',
        default_args=default_args,        
        tags= ['BCB', 'SPIM_1050_ODLT', 'Download', 'Mensual', '2026-08-31'],
        doc_md=doc_md,
        catchup=False,
        max_active_runs=1 )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000103')#ALL=True)
