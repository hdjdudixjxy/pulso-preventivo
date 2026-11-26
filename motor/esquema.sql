PRAGMA foreign_keys=ON;
CREATE TABLE metadata (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE asesores (id INTEGER PRIMARY KEY, agencia TEXT NOT NULL);
CREATE TABLE clientes (id INTEGER PRIMARY KEY, asesor_id INTEGER NOT NULL REFERENCES asesores,
    departamento TEXT NOT NULL, sector TEXT NOT NULL, mes_bajo INTEGER, alta TEXT NOT NULL);
CREATE TABLE productos (id TEXT PRIMARY KEY, moneda TEXT NOT NULL, frecuencia TEXT NOT NULL,
    tea_min REAL NOT NULL, tea_max REAL NOT NULL);
CREATE TABLE creditos (id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL REFERENCES clientes,
    producto_id TEXT NOT NULL REFERENCES productos, segmento TEXT NOT NULL, desembolso TEXT NOT NULL,
    principal_cent INTEGER NOT NULL CHECK(principal_cent>0), tea REAL NOT NULL, plazo INTEGER NOT NULL);
CREATE TABLE cronogramas (id INTEGER PRIMARY KEY, credito_id INTEGER NOT NULL REFERENCES creditos,
    version INTEGER NOT NULL, registrado TEXT NOT NULL, vigente_desde TEXT NOT NULL, motivo TEXT NOT NULL,
    UNIQUE(credito_id,version));
CREATE TABLE cuotas (cronograma_id INTEGER NOT NULL REFERENCES cronogramas, numero INTEGER NOT NULL,
    inicio_ciclo TEXT NOT NULL, vence TEXT NOT NULL, capital_cent INTEGER NOT NULL,
    interes_cent INTEGER NOT NULL, PRIMARY KEY(cronograma_id,numero));
CREATE TABLE abonos (id INTEGER PRIMARY KEY, credito_id INTEGER NOT NULL REFERENCES creditos,
    numero INTEGER NOT NULL, efectiva TEXT NOT NULL, registrada TEXT NOT NULL,
    importe_cent INTEGER NOT NULL CHECK(importe_cent>0), canal TEXT NOT NULL);
CREATE TABLE incidencias_fuente (id INTEGER PRIMARY KEY, agencia TEXT NOT NULL,
    detectada TEXT NOT NULL, resuelta TEXT);
CREATE INDEX abonos_cuota ON abonos(credito_id,numero,registrada);
CREATE INDEX versiones_credito ON cronogramas(credito_id,version);
CREATE TABLE gestiones (id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL REFERENCES clientes,
    credito_id INTEGER NOT NULL REFERENCES creditos, numero INTEGER NOT NULL, corte TEXT NOT NULL,
    fecha_accion TEXT NOT NULL, accion TEXT NOT NULL CHECK(accion IN ('contactado','observar','cerrar')),
    seguimiento TEXT, nota TEXT NOT NULL, asesor_id INTEGER NOT NULL REFERENCES asesores);
