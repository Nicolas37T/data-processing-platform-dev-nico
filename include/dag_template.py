import sys
import os
sys.path.append(os.path.expanduser("~"))
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from airflow.utils.dates import days_ago
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

dag = DAG(dag-id,
        #schedule_interval= schedule-to-replace,
        default_args=default_args,        
        tags= [tagsToReplace],
        catchup=False )

create_dag(dag, connection_id=connection-id,id_dag=dag-id)#ALL=True)