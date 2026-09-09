UPDATE report
   SET migrated_to = '{{ ti.xcom_pull(task_ids='pre_load', key='converted_to')}}',
       conversion_factor = '{{ ti.xcom_pull(task_ids='load', key='load_metadata')['conversion_factor'] }}'
 WHERE id_report = '{{ ti.xcom_pull(task_ids='get_migration_data', key='id_report')}}'
   AND ('{{ ti.xcom_pull(task_ids='pre_load', key='converted_to')}}' > migrated_to OR migrated_to IS NULL);