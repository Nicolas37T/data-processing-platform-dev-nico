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

doc_md = """## 📥 DAG Descarga: D_BO_000000213

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **SNIS** (Sistema Nacional de Información en Salud) |
| **📊 Dataset(s)** | `S_BOSNIS44_000789` |
| **📝 Nombre Dataset** | Ingresos y Egresos por Servicio de Internacion |
| **📁 Archivo** | Ingresos y Egresos por Servicio de Internacion |
| **⚙️ Tipo Descarga** | Tipo IV (multi_file_download_template) |
| **📅 Última Descarga** | **2026-08-10** |
| **⏱️ Frecuencia** | `0 4 2,10,20 * *` |
| **🧭 Ruta Web** | - |
| **🌐 Portal Web** | [Abrir portal ↗](https://estadisticas.minsalud.gob.bo/Reportes_Dinamicos/Menu_rep_dinamicos.aspx) |
"""

dag = DAG('D_BO_000000213',
        schedule= '0 4 2,10,20 * *',
        default_args=default_args,        
        tags= ['SNIS', 'S_BOSNIS44_000789', 'Download', 'Mensual', '2026-08-10'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000213')#ALL=True)
