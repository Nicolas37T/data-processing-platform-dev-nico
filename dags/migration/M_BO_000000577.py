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

doc_md = """## 📋 DAG Migration: M_BO_000000577

- **Fuente:** **BCB**
- **Tipo:** Migration
"""

dag = DAG('M_BO_000000577',
        #schedule= schedule-to-replace,
        default_args=default_args,        
        tags= ['BCB', 'Migration', '2026-09-15'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='M_BO_000000577')#ALL=True)
