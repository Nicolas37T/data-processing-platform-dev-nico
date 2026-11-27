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

doc_md = """## 📥 DAG Descarga: D_BO_000000015

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **INE** (Instituto Nacional de Estadística) |
| **📊 Dataset(s)** | `S_BOINE_44_000302` |
| **📝 Nombre Dataset** | Precios Promedio de Productos y Servicios por Departamento |
| **📁 Archivo** | Precios Promedio de Productos por Ciudades |
| **⚙️ Tipo Descarga** | Tipo I (file_download_template) |
| **📅 Última Descarga** | **2026-07-31** |
| **⏱️ Frecuencia** | `0 10 * * 1,3,4` |
| **🧭 Ruta Web** | - |
| **🌐 Portal Web** | [Abrir portal ↗](https://www.ine.gob.bo/index.php/ciudades-y-conurbaciones/) |
"""

dag = DAG('D_BO_000000015',
        schedule= '0 10 * * 1,3,4',
        default_args=default_args,        
        tags= ['INE', 'S_BOINE_44_000302', 'Download', 'Mensual', '2026-07-31'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000015')#ALL=True)
