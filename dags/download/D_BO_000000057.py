import sys
import os
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/dags')
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.multi_file_download_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

doc_md = """## 📥 DAG Descarga: D_BO_000000057

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **ASFI** (Autoridad de Supervisión del Sistema Financiero) |
| **📊 Dataset(s)** | `S_BOASFI22_000529` |
| **📝 Nombre Dataset** | Información de Fondos de Inversión |
| **📁 Archivo** | Información de Fondos de Inversión |
| **⚙️ Tipo Descarga** | Tipo IV (multi_file_download_template) |
| **📅 Última Descarga** | **2026-08-30** |
| **⏱️ Frecuencia** | `40 8 * * 4` |
| **🧭 Ruta Web** | - |
| **🌐 Portal Web** | [Abrir portal ↗](https://appweb2.asfi.gob.bo/PaginasPublicas2/vistareportevalores/fondosInversionGeneral.aspx) |
"""

dag = DAG('D_BO_000000057',
        schedule= '40 8 * * 4',
        default_args=default_args,        
        tags= ['ASFI', 'S_BOASFI22_000529', 'Download', '2026-08-30'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000057')#ALL=True)
