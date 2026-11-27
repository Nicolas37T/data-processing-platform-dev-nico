import sys
import os
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/dags')
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.data_download_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

doc_md = """## 📥 DAG Descarga: D_BO_000000271

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **FIFA** (Fédération Internationale de Football Association) |
| **📊 Dataset(s)** | `S_MUFIFA44_000530` |
| **📝 Nombre Dataset** | Clasificación Mundial Fifa |
| **📁 Archivo** | Clasificación Mundial FIFA Masculina |
| **⚙️ Tipo Descarga** | Tipo III (data_download_template) |
| **📅 Última Descarga** | **2026-06-11** |
| **⏱️ Frecuencia** | `6 9 8,16,24 * *` |
| **🧭 Ruta Web** | - |
| **🌐 Portal Web** | [Abrir portal ↗](https://es.fifa.com/fifa-world-ranking/ranking-table/men/) |
"""

dag = DAG('D_BO_000000271',
        schedule= '6 9 8,16,24 * *',
        default_args=default_args,        
        tags= ['FIFA', 'S_MUFIFA44_000530', 'Download', 'Mensual', '2026-06-11'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000271')#ALL=True)
