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

doc_md = """## 📥 DAG Descarga: D_BO_000000480

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **CNDC** (Comité Nacional de Despacho de Carga) |
| **📊 Dataset(s)** | `S_BOCNDC11_000445` |
| **📝 Nombre Dataset** | Generación Diaria y Generación Máxima |
| **📁 Archivo** | Generación Diaria y Generación Máxima |
| **⚙️ Tipo Descarga** | Tipo I (file_download_template) |
| **📅 Última Descarga** | **2026-11-05** |
| **⏱️ Frecuencia** | `16 8 * * 5` |
| **🧭 Ruta Web** | Inicio: Estadisticas>>Categorias>>Diaria>>Generación Últimos 12 Meses>>Generación Últimos 12 Meses – #Fecha |
| **🌐 Portal Web** | [Abrir portal ↗](https://www.cndc.bo/estadisticas/index.php) |
"""

dag = DAG('D_BO_000000480',
        schedule= '16 8 * * 5',
        default_args=default_args,        
        tags= ['CNDC', 'S_BOCNDC11_000445', 'Download', 'Diario', '2026-11-05'],
        doc_md=doc_md,
        catchup=False,
        max_active_runs=1 )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000480')#ALL=True)
