-- populate broken_url table
INSERT INTO public.broken_url (
            id_file, url, file_name, file_code, execution_date)
    VALUES (
            '{{ ti.xcom_pull(task_ids='read_download_data', key='file_id')}}',
            '{{ ti.xcom_pull(task_ids='read_download_data', key='file_url')}}',
            '{{ ti.xcom_pull(task_ids='read_download_data', key='file_name')}}',
            {{ params.file_code }},
            '{{dag_run.start_date}}'
        );
   
             