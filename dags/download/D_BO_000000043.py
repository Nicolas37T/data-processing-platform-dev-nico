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

doc_md = """## 📥 DAG Descarga: D_BO_000000043

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **FDTA-Valles** (FDTA-Valles) |
| **📊 Dataset(s)** | `SPIM_13001_IDPCB` |
| **📝 Nombre Dataset** | Daily Prices Of Cocoa Beans |
| **📁 Archivo** | icco daily prices of Cocoa Beans |
| **⚙️ Tipo Descarga** | Tipo II (direct_download_template) |
| **📅 Última Descarga** | **2026-10-01** |
| **⏱️ Frecuencia** | `42 8 * * 5` |
| **🧭 Ruta Web** | Inicio: Statics>>Cocoa Daily Prices |
| **🌐 Portal Web** | [Abrir portal ↗](https://www.icco.org/statistics/) |
"""

dag = DAG('D_BO_000000043',
        schedule= '42 8 * * 5',
        default_args=default_args,        
        tags= ['FDTA-Valles', 'SPIM_13001_IDPCB', 'Download', 'Diario', '2026-10-01'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000043')#ALL=True)
