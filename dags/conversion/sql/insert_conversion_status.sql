{% set items = ti.xcom_pull(task_ids=params.task, key=params.key) %}
{% if items %}
INSERT INTO public.conversion (
    id_report, type, conversion_date, id_download,
    {% for item in items %}{{ item.status }}{% if not loop.last %}, {% endif %}{% endfor %}
) VALUES (
    '{{ ti.xcom_pull(task_ids='get_conversion_data', key='id_report')}}',
    '{{ ti.xcom_pull(task_ids='get_conversion_data', key='type')}}',
    '{{dag_run.start_date}}',
    '{{ ti.xcom_pull(task_ids='get_conversion_data', key='id_download')}}',
    {% for item in items %}'{{ item.path }}'{% if not loop.last %}, {% endif %}{% endfor %}
);
{% else %}
INSERT INTO public.conversion (
    id_report, type, conversion_date, no_updates, id_download
) VALUES (     
     '{{ ti.xcom_pull(task_ids='get_conversion_data', key='id_report')}}',
     '{{ ti.xcom_pull(task_ids='get_conversion_data', key='type')}}',
     '{{dag_run.start_date}}',
     'no_updates',
     '{{ ti.xcom_pull(task_ids='get_conversion_data', key='id_download')}}'
);
{% endif %}