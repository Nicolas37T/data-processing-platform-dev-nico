{% set items = ti.xcom_pull(task_ids='store_files', key='files_dicts') %}
{% for item in items %}

INSERT INTO public.download (
    id_file, id_user, type, path, downloaded_to, state, download_date, urls, type_file, download_hash
) VALUES (
     --{{ loop.index }},
     '{{ ti.xcom_pull(task_ids='read_download_data', key='file_id')}}',
     {{ params.id_user }},
     '{{ ti.xcom_pull(task_ids='read_download_data', key='file_type')}}',
     '{{ item.datax_file_path }}',
     '{{ item.updated_to }}',
     {{ params.state}},
     '{{dag_run.start_date}}',
     '{{ item.download_url }}',
     {{ params.type_file}},
     '{{ item.file_hash }}'
)
RETURNING id_download, path;
{% endfor %}
