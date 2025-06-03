-- populate review table
INSERT INTO public.review (
            id_file, id_user, review_date, type)
    VALUES ('{{ ti.xcom_pull(task_ids='read_download_data', key='file_id')}}',
            {{ params.id_user }},
            '{{dag_run.start_date}}',
            {{ params.type}}
        );
   
             