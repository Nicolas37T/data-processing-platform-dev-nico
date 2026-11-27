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

doc_md = """## 📥 DAG Descarga: D_BO_000000041

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **BCB** (Banco Central de Bolivia) |
| **📊 Dataset(s)** | `S_BOBCB_22_000778` |
| **📝 Nombre Dataset** | Old224 Tasas Nominales Empresas |
| **📁 Archivo** | Información Sobre El Interés Que Pagan Las Empresas Por Sus Préstamos Con Entidades Financieras |
| **⚙️ Tipo Descarga** | Tipo I (file_download_template) |
| **📅 Última Descarga** | **2026-08-02** |
| **⏱️ Frecuencia** | `33 10 * * 1-5` |
| **🧭 Ruta Web** | - |
| **🌐 Portal Web** | [Abrir portal ↗](https://www.bcb.gob.bo/?q=tasas_interes) |
"""

dag = DAG('D_BO_000000041',
        schedule= '33 10 * * 1-5',
        default_args=default_args,        
        tags= ['BCB', 'S_BOBCB_22_000778', 'Download', 'Semanal', '2026-08-02'],
        doc_md=doc_md,
        catchup=False,
        max_active_runs=1 )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000041')#ALL=True)
