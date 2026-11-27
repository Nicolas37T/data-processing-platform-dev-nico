import sys
import os
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/dags')
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.direct_download_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

doc_md = """## 📥 DAG Descarga: D_BO_000000055

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **ASFI** (Autoridad de Supervisión del Sistema Financiero) |
| **📊 Dataset(s)** | `S_BOASFI_44_000762` |
| **📝 Nombre Dataset** | Cantidad de Puntos de Atención de Entidades Financieras por Departamento |
| **📁 Archivo** | Ubicación de Puntos de Atención de Entidades Financieras |
| **⚙️ Tipo Descarga** | Tipo II (direct_download_template) |
| **📅 Última Descarga** | **2026-07-31** |
| **⏱️ Frecuencia** | `4 11 L * *` |
| **🧭 Ruta Web** | - |
| **🌐 Portal Web** | [Abrir portal ↗](https://appweb2.asfi.gob.bo/PaginasPublicas2/VistaPAF/UbicacionPAF.aspx) |
"""

dag = DAG('D_BO_000000055',
        schedule= '4 11 L * *',
        default_args=default_args,        
        tags= ['ASFI', 'S_BOASFI_44_000762', 'Download', 'Mensual', '2026-07-31'],
        doc_md=doc_md,
        catchup=False,
        max_active_runs=1 )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000055')#ALL=True)
