--sql para obtener los datos de la descarga
SELECT path,
        main_url, 
        id_file,
        type,
        publication_frequency,
        updated_to,
        name,
        last_file_path,
        short_name,
        key_words
FROM file 
WHERE code = {{ params.file_code}}
