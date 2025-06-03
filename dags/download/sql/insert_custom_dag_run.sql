-- populate dag_run table
INSERT INTO public.dag_run (
            id_dag, execution_date, state, run_id, run_type, id_file, file_name, file_url, file_path)
    VALUES ( '{{ dag.dag_id }}',
             '{{dag_run.start_date}}',
              {{ params.state }}, 
             '{{dag_run.run_id}}',
             '{{dag_run.run_type}}',
             '{{ ti.xcom_pull(task_ids='read_download_data', key='file_id')}}',
             '{{ ti.xcom_pull(task_ids='read_download_data', key='file_name')}}',
             '{{ ti.xcom_pull(task_ids='read_download_data', key='file_url')}}',
             '{{ ti.xcom_pull(key='return_value', task_ids='get_download_data')[0][0] | replace("\\", "\\\\")}}'
            );  