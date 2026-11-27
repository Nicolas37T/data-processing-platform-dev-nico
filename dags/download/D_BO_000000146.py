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

doc_md = """## 📥 DAG Descarga: D_BO_000000146

| Parámetro | Detalle |
|---|---|
| **🏛️ Fuente** | **INE** (Instituto Nacional de Estadística) |
| **📊 Dataset(s)** | `S_BOINE_66_000485` |
| **📝 Nombre Dataset** | Índice de la Cantidad de Producción de Minerales |
| **📁 Archivo** | Bolivia – Índice de Volumen de Producción de Minerales por Tipo de Mineral según Año y Mes 1990 – 2024 |
| **⚙️ Tipo Descarga** | Tipo I (file_download_template) |
| **📅 Última Descarga** | **2025-12-31** |
| **⏱️ Frecuencia** | `21 11 * * 1,3,4` |
| **🧭 Ruta Web** | Inicio: Estadisticas Economicas>>HIDROCARBUROS/MINERÍA>>Mineria??AÑO REFERENCIAL 2017 (BASE MÓVIL)>>Cuadros Estadísticos>>Indicadores>>Bolivia: Índice de volumen de producción de minerales por tipo de mineral según mes, 2017 – 2026 |
| **🌐 Portal Web** | [Abrir portal ↗](https://www.ine.gob.bo/index.php/estadisticas-economicas/hidrocarburos-mineria/mineria-cuadros-estadisticos/) |
"""

dag = DAG('D_BO_000000146',
        schedule= '21 11 * * 1,3,4',
        default_args=default_args,        
        tags= ['INE', 'S_BOINE_66_000485', 'Download', 'Mensual', '2025-12-31'],
        doc_md=doc_md,
        catchup=False )

create_dag(dag, connection_id='platform_db',id_dag='D_BO_000000146')#ALL=True)
