-- platform_db schema
-- Created from Bolivia production database structure.
-- Run once against the platform_db database on first deploy.

-- ─── Independent tables ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.source (
    id_source   SERIAL PRIMARY KEY,
    name        TEXT,
    short_name  TEXT,
    homepage    TEXT NOT NULL,
    creation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    observations  TEXT
);

CREATE TABLE IF NOT EXISTS public.tipousuario (
    idtipousuario    SERIAL PRIMARY KEY,
    tipo             VARCHAR(255) NOT NULL,
    tiempoactualizar INTEGER NOT NULL,
    orden            INTEGER
);

CREATE TABLE IF NOT EXISTS public.usuario (
    idusuario        SERIAL PRIMARY KEY,
    idtipousuario    INTEGER NOT NULL REFERENCES tipousuario(idtipousuario),
    nombre           VARCHAR(255) NOT NULL,
    apellido         VARCHAR(255) NOT NULL,
    email            VARCHAR(255),
    login            VARCHAR(255) NOT NULL,
    password         VARCHAR(255) NOT NULL,
    estado           VARCHAR(255) NOT NULL,
    tiempoacumulado  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.cubo (
    idcubo          SERIAL PRIMARY KEY,
    codigospim      VARCHAR(255) NOT NULL,
    codigoanalyze   VARCHAR(255) NOT NULL,
    fuente          VARCHAR(255) NOT NULL,
    frecuenciadatos VARCHAR(255) NOT NULL,
    estado          VARCHAR(255) NOT NULL,
    tiempo          INTEGER DEFAULT 30
);

-- ─── Core pipeline tables ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.file (
    id_file             SERIAL PRIMARY KEY,
    id_source           INTEGER NOT NULL,
    name                TEXT,
    code                VARCHAR(255),
    main_url            TEXT,
    path                TEXT,
    type                VARCHAR(255),
    specific_url        TEXT,
    alternate_url       TEXT,
    navigation_path     TEXT DEFAULT 'Inicio>>',
    publication_frequency VARCHAR(255) NOT NULL,
    priority            INTEGER,
    state               VARCHAR(255) NOT NULL,
    creation_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    observations        TEXT,
    updated_to          TEXT,
    last_file_path      TEXT,
    last_file_url       TEXT,
    schedule_interval   TEXT,
    publication_date    VARCHAR(255),
    key_words           VARCHAR(255),
    section_path        TEXT DEFAULT 'Seccion>>',
    short_name          VARCHAR(255),
    download_type       VARCHAR(255),
    assigned_to         VARCHAR(255),
    color               VARCHAR(255),
    task                VARCHAR(255),
    is_false_positive   BOOLEAN DEFAULT TRUE,
    accion              VARCHAR(255),
    delay               VARCHAR,
    general_status      VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS public.report (
    id_report             BIGSERIAL PRIMARY KEY,
    id_file               BIGINT NOT NULL,
    name                  TEXT,
    publication_data      VARCHAR(255),
    publication_frequency VARCHAR(255),
    creation_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    observations          TEXT,
    code                  VARCHAR(255),
    path                  TEXT,
    converted_report_path TEXT,
    converted_to          DATE,
    key_words             VARCHAR(255),
    type                  VARCHAR(255),
    "isActive"            BOOLEAN DEFAULT FALSE,
    storage_table         TEXT,
    file_extension        VARCHAR(120),
    replacement_table     VARCHAR,
    compare_dates         BOOLEAN NOT NULL DEFAULT TRUE,
    page_number           BIGINT DEFAULT 0,
    decimal_separator     TEXT,
    conversion_factor     NUMERIC,
    migrated_to           DATE DEFAULT '1990-01-01',
    load_scope            TEXT,
    text_normalization    BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS public.data_base (
    id_data_base   BIGSERIAL PRIMARY KEY,
    name           TEXT UNIQUE,
    db_code        VARCHAR(50) NOT NULL UNIQUE,
    data_frequency VARCHAR(50) NOT NULL,
    update_frequenc VARCHAR(50),
    data_since     VARCHAR(120),
    updated_to     VARCHAR(120),
    source         TEXT,
    acronym        VARCHAR(50),
    source_language VARCHAR(120),
    creation_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    observations   TEXT,
    csv_sql        TEXT,
    description    TEXT,
    free_updated_to VARCHAR(120),
    next_update_date VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS public.download (
    id_download   SERIAL PRIMARY KEY,
    id_file       INTEGER NOT NULL,
    id_user       INTEGER,
    type          VARCHAR(255),
    path          TEXT NOT NULL,
    downloaded_to DATE NOT NULL,
    next_download DATE,
    state         VARCHAR(255),
    download_date DATE NOT NULL,
    creation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    observations  TEXT,
    urls          TEXT,
    type_file     TEXT,
    download_hash TEXT
);

CREATE TABLE IF NOT EXISTS public.conversion (
    id_conversion         BIGSERIAL PRIMARY KEY,
    id_report             BIGINT REFERENCES report(id_report),
    file_extension        VARCHAR(100),
    conversion_path       TEXT,
    converted_to          VARCHAR(100),
    type                  VARCHAR(120),
    creation_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    observations          TEXT,
    corrupted_file        TEXT,
    unextractable_report  TEXT,
    report_structure_change TEXT,
    conversion_date       DATE,
    no_updates            TEXT,
    id_download           BIGINT,
    totals_mismatch       BOOLEAN NOT NULL DEFAULT FALSE,
    fixed                 BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS public.migration (
    id_migration  BIGSERIAL PRIMARY KEY,
    id_report     INTEGER,
    migrated_to   VARCHAR(255),
    creation_date DATE DEFAULT CURRENT_DATE,
    updated_date  DATE DEFAULT CURRENT_DATE,
    status        VARCHAR(255),
    observations  TEXT,
    id_conversion INTEGER,
    migration_date DATE
);

CREATE TABLE IF NOT EXISTS public.product (
    id_product    BIGSERIAL PRIMARY KEY,
    id_report     BIGINT,
    id_data_base  BIGINT,
    updated_to    VARCHAR(255),
    creation_date DATE DEFAULT CURRENT_DATE,
    updated_date  DATE DEFAULT CURRENT_DATE,
    status        VARCHAR(255),
    observations  TEXT,
    execution_date DATE
);

-- ─── Logging and monitoring tables ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.dag_run (
    id_dag_run    SERIAL PRIMARY KEY,
    id_dag        VARCHAR(255),
    execution_date TIMESTAMP NOT NULL,
    state         TEXT,
    run_id        VARCHAR(250),
    run_type      VARCHAR(50),
    creation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    observations  TEXT,
    id_file       INTEGER,
    file_name     TEXT,
    file_url      TEXT,
    file_path     TEXT
);

CREATE TABLE IF NOT EXISTS public.dag_run_exceptions (
    identifier    SERIAL PRIMARY KEY,
    execute_date  TIMESTAMP NOT NULL,
    file_code     VARCHAR(255) NOT NULL,
    file_name     VARCHAR(255) NOT NULL,
    spim_code     TEXT NOT NULL,
    failed_task   VARCHAR(255) NOT NULL,
    exception     TEXT NOT NULL,
    log_path      TEXT NOT NULL,
    host          VARCHAR(255) NOT NULL,
    creation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    observations  TEXT
);

CREATE TABLE IF NOT EXISTS public.conversion_exceptions (
    id_conversion_exceptions BIGSERIAL PRIMARY KEY,
    id_report       BIGINT,
    conversion_date DATE NOT NULL,
    report_name     VARCHAR(255) NOT NULL,
    file_code       VARCHAR(100) NOT NULL,
    db_code         VARCHAR(100),
    failed_task     VARCHAR(255) NOT NULL,
    exceptions      TEXT,
    creation_date   TIMESTAMP NOT NULL DEFAULT now(),
    update_date     TIMESTAMP NOT NULL DEFAULT now(),
    observations    TEXT
);

CREATE TABLE IF NOT EXISTS public.migration_exceptions (
    id_migration_exceptions BIGSERIAL PRIMARY KEY,
    id_report      BIGINT NOT NULL,
    migration_date DATE NOT NULL,
    migration_code VARCHAR(255) NOT NULL,
    failed_task    VARCHAR(255),
    exceptions     TEXT,
    creation_date  TIMESTAMP NOT NULL DEFAULT now(),
    updated_date   TIMESTAMP NOT NULL DEFAULT now(),
    observations   TEXT
);

CREATE TABLE IF NOT EXISTS public.product_exceptions (
    id_product_exceptions BIGSERIAL PRIMARY KEY,
    id_report      BIGINT,
    id_data_base   BIGINT,
    failed_task    VARCHAR(255),
    exceptions     TEXT,
    creation_date  TIMESTAMP DEFAULT now(),
    updated_date   TIMESTAMP DEFAULT now(),
    observations   TEXT,
    execution_date DATE
);

CREATE TABLE IF NOT EXISTS public.alerts (
    id_alert      SERIAL PRIMARY KEY,
    short_name    VARCHAR(255),
    db_code       VARCHAR(50),
    file_code     VARCHAR(255),
    report_code   VARCHAR(255),
    name_data_base TEXT,
    name_file     TEXT,
    publication_frequency VARCHAR(255),
    navigation_path TEXT,
    updated_to    DATE,
    main_url      TEXT,
    alert_date    TIMESTAMP DEFAULT now(),
    natural_delay VARCHAR(50),
    status        VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS public.broken_url (
    id_broken_url  SERIAL PRIMARY KEY,
    id_file        INTEGER NOT NULL REFERENCES file(id_file),
    url            TEXT,
    file_name      VARCHAR(250),
    file_code      VARCHAR(100),
    execution_date TIMESTAMP NOT NULL,
    creation_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    observations   TEXT
);

CREATE TABLE IF NOT EXISTS public.data_base_report (
    db_code     VARCHAR(255) NOT NULL,
    report_code VARCHAR(255) NOT NULL,
    PRIMARY KEY (db_code, report_code)
);

-- ─── Supporting tables ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.review (
    id_review     SERIAL PRIMARY KEY,
    id_file       INTEGER NOT NULL,
    id_user       INTEGER NOT NULL,
    review_date   DATE NOT NULL,
    creation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    observations  TEXT,
    type          VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS public.delay (
    id_delay       SERIAL PRIMARY KEY,
    id_source      INTEGER NOT NULL REFERENCES source(id_source),
    id_file        INTEGER NOT NULL REFERENCES file(id_file),
    frecuency_delay VARCHAR(50),
    delay          INTEGER,
    creation_date  TIMESTAMP DEFAULT now(),
    update_date    TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.assignment (
    id_assignment       SERIAL PRIMARY KEY,
    spim_code           TEXT,
    web                 TEXT,
    date_to             TEXT,
    assignment_date     DATE,
    updater             TEXT,
    state               TEXT,
    fecha_creacion      DATE DEFAULT now(),
    fecha_modificacion  DATE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.resettiempos (
    idresettiempos SERIAL PRIMARY KEY,
    idusuario      INTEGER NOT NULL REFERENCES usuario(idusuario),
    idtipousuario  INTEGER NOT NULL,
    fecha          DATE NOT NULL,
    tiempo         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS public.actualizacion (
    idactualizacion  SERIAL PRIMARY KEY,
    idcubo           INTEGER NOT NULL REFERENCES cubo(idcubo),
    idusuario        INTEGER NOT NULL REFERENCES usuario(idusuario),
    idresponsable    INTEGER NOT NULL REFERENCES usuario(idusuario),
    gestion          INTEGER NOT NULL,
    semana           INTEGER NOT NULL,
    fechaactualizacion DATE,
    fechadescarga    DATE NOT NULL,
    fechacreacion    DATE NOT NULL,
    fechaproximaact  DATE NOT NULL,
    web              TEXT NOT NULL,
    tipoasignacion   VARCHAR(255) NOT NULL,
    fechaini         DATE,
    fechafin         DATE,
    observaciones    TEXT,
    datosa           DATE,
    estado           VARCHAR(255) NOT NULL,
    tiempoproceso    INTEGER,
    cantidad         INTEGER NOT NULL DEFAULT 0,
    fechaprimera     DATE
);

CREATE TABLE IF NOT EXISTS public."update" (
    id_update           SERIAL PRIMARY KEY,
    id_cube             INTEGER NOT NULL,
    id_dependent_cube   INTEGER NOT NULL,
    creation_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    update_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    observations        TEXT
);
