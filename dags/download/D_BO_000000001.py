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

doc_md = """## 📥 DAG Descarga: D_BO_000000001

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **ASFI** (Autoridad de Supervisión del Sistema Financiero) |
| **📊 Dataset(s)** | `SPIM_0023_FI, SPIM_0026_ORBBV` |
| **📝 Nombre Dataset** | Fondos de Inversión / Operaciones en Ruedo de Bolsa |
| **📁 Archivo** | Boletin - Valores |
| **⚙️ Tipo Descarga** | Tipo I (file_download_template) |
| **📅 Última Descarga** | **2026-04-30** |
| **⏱️ Frecuencia** | `0 10,15 * * 2` |
| **🧭 Ruta Web** | Inicio >> |
| **🌐 Portal Web** | [Abrir portal ↗](https://www.asfi.gob.bo/node/498) |
"""

dag = DAG('D_BO_000000001',
        schedule= '0 10,15 * * 2',
        default_args=default_args,        
        tags= ['ASFI', 'SPIM_0023_FI', 'SPIM_0026_ORBBV', 'Download', 'Mensual', '2026-04-30'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000001')#ALL=True)
