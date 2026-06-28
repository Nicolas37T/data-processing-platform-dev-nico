UPDATE file
   SET updated_to = '{{ ti.xcom_pull(task_ids='getDateUpdated', key='dataDate')}}',
       last_file_path = '{{ ti.xcom_pull(task_ids='storeFiles', key='paths')}}', 
       last_file_url  = '{{(ti.xcom_pull(task_ids='getFileUrl', key='lastFileLinks'))|join(';')}}',
       schedule_interval = '{{ dag.schedule }}'
WHERE id_file = '{{ ti.xcom_pull(task_ids='readDownloadData', key='fileId')}}'

