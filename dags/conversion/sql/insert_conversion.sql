{% set items = ti.xcom_pull(task_ids='structure_review', key='corrupted_files_path') %}
{% set converted_file = ti.xcom_pull(task_ids='report_data_validation', key='converted_file') %}
{% set id_dl = ti.xcom_pull(task_ids='get_conversion_data', key='id_download') %}
{% if items %}
INSERT INTO public.conversion (
    id_report, type, file_extension, conversion_path, converted_to, totals_mismatch, conversion_date, id_download,
    {% for item in items %}{{ item.status }}{% if not loop.last %}, {% endif %}{% endfor %}
) VALUES (     
     '{{ ti.xcom_pull(task_ids='get_conversion_data', key='id_report')}}',
     '{{ ti.xcom_pull(task_ids='get_conversion_data', key='type')}}',
     '{{ converted_file.file_extension }}',
     '{{ converted_file.conversion_path }}',
     '{{ converted_file.converted_to }}',
     '{{ converted_file.totals_mismatch }}',
     '{{dag_run.start_date}}',
     {{ id_dl if (id_dl and id_dl != 'None') else 'NULL' }},
    {% for item in items %}'{{ item.path }}'{% if not loop.last %}, {% endif %}{% endfor %}
)
{% else %}
INSERT INTO public.conversion (
    id_report, type, file_extension, conversion_path, converted_to, totals_mismatch, conversion_date, id_download
) VALUES (     
     '{{ ti.xcom_pull(task_ids='get_conversion_data', key='id_report')}}',
     '{{ ti.xcom_pull(task_ids='get_conversion_data', key='type')}}',
     '{{ converted_file.file_extension }}',
     '{{ converted_file.conversion_path }}',
     '{{ converted_file.converted_to }}',
     '{{ converted_file.totals_mismatch }}',
     '{{dag_run.start_date}}',
     {{ id_dl if (id_dl and id_dl != 'None') else 'NULL' }}
)
{% endif %}
RETURNING id_conversion, conversion_path;