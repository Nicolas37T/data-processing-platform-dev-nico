import sys
import os
sys.path.append(os.path.expanduser("~"))
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.data_download_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

dag = DAG('D_BO_000000485',
        schedule= '0 8 * * 5',
        default_args=default_args,        
        tags= ['BCB', 'Download'],
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000485')#ALL=True)