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

doc_md = """<h3>📥 DAG Descarga: <b>D_BO_000000462</b></h3>

<table style="width: 100%; border-collapse: collapse; font-size: 13px;">
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold; width: 32%;">🏛️ Fuente</td>
    <td style="padding: 6px;"><span style="background: #1e3a8a; color: #93c5fd; padding: 2px 8px; border-radius: 4px; font-weight: bold;">ADA</span> (Asociación de Avicultores)</td>
  </tr>
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold;">📊 Dataset(s)</td>
    <td style="padding: 6px;"><span style="background: #064e3b; color: #6ee7b7; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-right: 4px;">S_BOADA_11_000730</span> <span style="background: #064e3b; color: #6ee7b7; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-right: 4px;">S_BOADA_11_000731</span></td>
  </tr>
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold;">📝 Nombre Dataset</td>
    <td style="padding: 6px;">Evolucion del Precio del Pollo - Santa Cruz / Precios de Insumos Alimentos para Pollo - Santa Cruz</td>
  </tr>
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold;">📁 Archivo</td>
    <td style="padding: 6px;">Boletín Referencial Precios Avícolas</td>
  </tr>
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold;">⚙️ Tipo Descarga</td>
    <td style="padding: 6px;">Tipo I (file_download_template)</td>
  </tr>
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold;">📅 Última Descarga</td>
    <td style="padding: 6px;"><b style="color: #38bdf8;">2026-09-04</b></td>
  </tr>
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold;">⏱️ Frecuencia</td>
    <td style="padding: 6px;">0 17 * * *</td>
  </tr>
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold;">🧭 Ruta Web</td>
    <td style="padding: 6px;">Inicio>>descargar</td>
  </tr>
  <tr style="border-bottom: 1px solid #334155;">
    <td style="padding: 6px; font-weight: bold;">🌐 Portal Web</td>
    <td style="padding: 6px;"><a href="https://www.adascz.com.bo/" target="_blank" style="color: #60a5fa; text-decoration: underline;">Abrir portal ↗</a></td>
  </tr>
</table>
"""

dag = DAG('D_BO_000000462',
        schedule= '0 17 * * *',
        default_args=default_args,        
        tags= ['ADA', 'S_BOADA_11_000730', 'S_BOADA_11_000731', 'Download', '2026-09-04'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000462')#ALL=True)
