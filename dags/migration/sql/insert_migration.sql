{% set converted_to = ti.xcom_pull(task_ids='pre_load', key='converted_to') %}
INSERT INTO public.migration (
    id_report, migrated_to, id_conversion, migration_date
) VALUES (     
     '{{ ti.xcom_pull(task_ids='get_migration_data', key='id_report')}}',
     '{{ ti.xcom_pull(task_ids='pre_load', key='converted_to')}}',
     '{{ ti.xcom_pull(task_ids='get_migration_data', key='id_conversion')}}',
     '{{dag_run.start_date}}'
);