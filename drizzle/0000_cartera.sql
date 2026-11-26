CREATE TABLE metadata (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
--> statement-breakpoint
CREATE TABLE asesores (id INTEGER PRIMARY KEY, agencia TEXT NOT NULL);
--> statement-breakpoint
CREATE TABLE clientes (id INTEGER PRIMARY KEY, asesor_id INTEGER NOT NULL REFERENCES asesores,
    departamento TEXT NOT NULL, sector TEXT NOT NULL, mes_bajo INTEGER, alta TEXT NOT NULL);
--> statement-breakpoint
CREATE TABLE productos (id TEXT PRIMARY KEY, moneda TEXT NOT NULL, frecuencia TEXT NOT NULL,
    tea_min REAL NOT NULL, tea_max REAL NOT NULL);
--> statement-breakpoint
CREATE TABLE creditos (id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL REFERENCES clientes,
    producto_id TEXT NOT NULL REFERENCES productos, segmento TEXT NOT NULL, desembolso TEXT NOT NULL,
    principal_cent INTEGER NOT NULL CHECK(principal_cent>0), tea REAL NOT NULL, plazo INTEGER NOT NULL);
--> statement-breakpoint
CREATE TABLE cronogramas (id INTEGER PRIMARY KEY, credito_id INTEGER NOT NULL REFERENCES creditos,
    version INTEGER NOT NULL, registrado TEXT NOT NULL, vigente_desde TEXT NOT NULL, motivo TEXT NOT NULL,
    UNIQUE(credito_id,version));
--> statement-breakpoint
CREATE TABLE cuotas (cronograma_id INTEGER NOT NULL REFERENCES cronogramas, numero INTEGER NOT NULL,
    inicio_ciclo TEXT NOT NULL, vence TEXT NOT NULL, capital_cent INTEGER NOT NULL,
    interes_cent INTEGER NOT NULL, PRIMARY KEY(cronograma_id,numero));
--> statement-breakpoint
CREATE TABLE abonos (id INTEGER PRIMARY KEY, credito_id INTEGER NOT NULL REFERENCES creditos,
    numero INTEGER NOT NULL, efectiva TEXT NOT NULL, registrada TEXT NOT NULL,
    importe_cent INTEGER NOT NULL CHECK(importe_cent>0), canal TEXT NOT NULL);
--> statement-breakpoint
CREATE TABLE incidencias_fuente (id INTEGER PRIMARY KEY, agencia TEXT NOT NULL,
    detectada TEXT NOT NULL, resuelta TEXT);
--> statement-breakpoint
CREATE INDEX abonos_cuota ON abonos(credito_id,numero,registrada);
--> statement-breakpoint
CREATE INDEX versiones_credito ON cronogramas(credito_id,version);
--> statement-breakpoint
CREATE TABLE gestiones (id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL REFERENCES clientes,
    credito_id INTEGER NOT NULL REFERENCES creditos, numero INTEGER NOT NULL, corte TEXT NOT NULL,
    fecha_accion TEXT NOT NULL, accion TEXT NOT NULL CHECK(accion IN ('contactado','observar','cerrar')),
    seguimiento TEXT, nota TEXT NOT NULL, asesor_id INTEGER NOT NULL REFERENCES asesores);
--> statement-breakpoint
ALTER TABLE gestiones ADD COLUMN espacio TEXT;
--> statement-breakpoint
CREATE UNIQUE INDEX gestion_unica ON gestiones(espacio,corte,cliente_id);
--> statement-breakpoint
CREATE INDEX gestion_historial ON gestiones(espacio,cliente_id,fecha_accion);
--> statement-breakpoint
CREATE TABLE semanas(corte TEXT PRIMARY KEY);
--> statement-breakpoint
CREATE TABLE candidatos(
 corte TEXT NOT NULL REFERENCES semanas, asesor INTEGER NOT NULL REFERENCES asesores,
 cliente INTEGER NOT NULL REFERENCES clientes, credito INTEGER NOT NULL REFERENCES creditos,
 cuota INTEGER NOT NULL, version INTEGER NOT NULL, producto TEXT NOT NULL, segmento TEXT NOT NULL,
 vence TEXT NOT NULL, pendiente INTEGER NOT NULL, carga INTEGER NOT NULL, puntaje REAL NOT NULL,
 margen_ultimo REAL NOT NULL, habitual REAL NOT NULL, reciente REAL NOT NULL, evidencia TEXT NOT NULL,
 pregunta TEXT NOT NULL, baja INTEGER NOT NULL, anteriores INTEGER NOT NULL, evento TEXT, estacional INTEGER NOT NULL,
 PRIMARY KEY(corte,credito,cuota)
);
--> statement-breakpoint
CREATE INDEX candidatos_asesor ON candidatos(corte,asesor,cliente);
--> statement-breakpoint
CREATE TABLE revision(corte TEXT NOT NULL REFERENCES semanas, asesor INTEGER NOT NULL, cliente INTEGER NOT NULL, credito INTEGER NOT NULL, cuota INTEGER NOT NULL, motivo TEXT NOT NULL, PRIMARY KEY(corte,credito,cuota));
--> statement-breakpoint
CREATE INDEX revision_asesor ON revision(corte,asesor);
--> statement-breakpoint
CREATE TABLE importaciones(id INTEGER PRIMARY KEY, filas INTEGER NOT NULL);