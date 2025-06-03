UPDATE data_base
   SET updated_to = '{{ ti.xcom_pull(task_ids='post_load', key='last_date')}}',
       free_updated_to = '{{ ti.xcom_pull(task_ids='post_load', key='free_date')}}'
WHERE id_data_base = '{{ ti.xcom_pull(task_ids='get_product_data', key='id_data_base')}}'