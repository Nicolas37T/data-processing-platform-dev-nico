UPDATE file
   SET state = 'Actualizado',
       updated_to = '{{ ti.xcom_pull(task_ids='store_new_data', key='file_update')['updated_to'] }}',
       last_file_path = '{{ ti.xcom_pull(task_ids='store_new_data', key='file_update')['datax_file_path'] }}', 
       last_file_url  = '{{ ti.xcom_pull(task_ids='store_new_data', key='file_update')['download_url'] }}',
       schedule_interval = '{{ dag.schedule_interval }}'
WHERE id_file = '{{ ti.xcom_pull(task_ids='read_download_data', key='file_id')}}'


