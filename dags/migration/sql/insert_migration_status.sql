INSERT INTO public.migration (
    id_report, migration_date, id_conversion,status
) VALUES (
    '{{ ti.xcom_pull(task_ids='get_migration_data', key='id_report')}}',    
    '{{dag_run.start_date}}',
    '{{ ti.xcom_pull(task_ids='get_migration_data', key='id_conversion')}}',
    '{{params.status}}'
)