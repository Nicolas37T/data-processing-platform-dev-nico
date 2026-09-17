import sys
import os
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/dags')
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.migration_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

doc_md = """## 🚚 DAG Migración: M_BO_000000019

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **INE** (Instituto Nacional de Estadística) |
| **📊 Dataset(s)** | `SPIM_4015_PVCDCSD` |
| **📝 Nombre Dataset** | Producción, Venta, Consumo de Cemento según Departamento |
| **📄 Sub-reporte(s)** | Bolivia: Consumo de Cemento por Departamento según Año y Mes , (en Toneladas Metricas) |
| **🗄️ Tabla(s) Almacén** | `INE;DATA_D_BO_000000019_01` |
| **📅 Última Migración** | **2026-08-28** |
"""

dag = DAG('M_BO_000000019',
        #schedule= schedule-to-replace,
        default_args=default_args,        
        tags= ['INE', 'SPIM_4015_PVCDCSD', 'Migration', '2026-08-28'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='M_BO_000000019')#ALL=True)
