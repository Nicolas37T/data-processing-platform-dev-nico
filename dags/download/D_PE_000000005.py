import sys
import os
sys.path.append(os.path.expanduser("~"))
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from airflow.utils.dates import days_ago
from dags.templates.data_download_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

dag = DAG('D_PE_000000005',
        schedule_interval= '11 8 * * *',
        default_args=default_args,        
        tags= ['Download'],
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_PE_000000005')#ALL=True)