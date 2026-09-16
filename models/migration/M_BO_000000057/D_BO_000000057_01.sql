CREATE TABLE IF NOT EXISTS "%s"."%s"
(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  titulo1 text,
  fondo_inversion text,
  emisor text,
  nv1 text,
  fecha date,
  metrica character varying(255),
  unidad_metrica character varying(255),
  valor numeric,
  fecha_creacion date DEFAULT CURRENT_DATE,
  fecha_modificacion timestamp DEFAULT CURRENT_TIMESTAMP,
  observations text
);

CREATE OR REPLACE FUNCTION actualizar_fecha_modificacion()
RETURNS TRIGGER AS $$
BEGIN
  NEW.fecha_modificacion = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trigger_actualizar_fecha_modificacion
BEFORE UPDATE ON "%s"."%s"
FOR EACH ROW
EXECUTE FUNCTION actualizar_fecha_modificacion();
