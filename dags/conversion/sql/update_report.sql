UPDATE report
   SET converted_to = '{{ ti.xcom_pull(task_ids='report_data_validation', key='converted_file')['converted_to'] }}',
       converted_report_path = '{{ ti.xcom_pull(task_ids='report_data_validation', key='converted_file')['conversion_path'] }}',
       page_number = '{{ ti.xcom_pull(task_ids='report_data_validation', key='converted_file')['page_number'] }}',
       type = '{{ ti.xcom_pull(task_ids='get_conversion_data', key='type')}}' 
WHERE id_report = '{{ ti.xcom_pull(task_ids='get_conversion_data', key='id_report')}}'
  AND '{{ ti.xcom_pull(task_ids='report_data_validation', key='converted_file')['converted_to'] }}' > converted_to;


