import sys
import os
sys.path.append(os.path.expanduser("~"))
import pytz
from datetime import datetime
from airflow import DAG
from airflow.example_dags.plugins.workday import AfterWorkdayTimetable
from templates.conversion_template import create_dag

local_tz = pytz.timezone("America/La_Paz")
default_args = {'owner': 'datax',
                    'start_date': datetime(2024, 1, 1, tzinfo = local_tz),
                    'timetable': AfterWorkdayTimetable(),
                    'email_on_failure': False,
                    'email_on_success': False,
                    'email_on_retry': False,                    
                    'retries': 0
                    }

dag = DAG('C_BO_000000487',
        #schedule= schedule-to-replace,
        default_args=default_args,        
        tags= ['BCB', 'Conversion'],
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='C_BO_000000487')#ALL=True)
