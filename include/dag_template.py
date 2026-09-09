import sys
import os
sys.path.append('/opt/airflow')
sys.path.append('/opt/airflow/dags')
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.dag-template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

doc_md = """docMdToReplace"""

dag = DAG(dag-id,
        #schedule= schedule-to-replace,
        default_args=default_args,        
        tags= [tagsToReplace],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id=connection-id,id_dag=dag-id)#ALL=True)