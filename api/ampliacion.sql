ALTER TABLE gestiones ADD COLUMN espacio TEXT;
CREATE UNIQUE INDEX gestion_unica ON gestiones(espacio,corte,cliente_id);
CREATE INDEX gestion_historial ON gestiones(espacio,cliente_id,fecha_accion);
CREATE TABLE semanas(corte TEXT PRIMARY KEY);
CREATE TABLE candidatos(
 corte TEXT NOT NULL REFERENCES semanas, asesor INTEGER NOT NULL REFERENCES asesores,
 cliente INTEGER NOT NULL REFERENCES clientes, credito INTEGER NOT NULL REFERENCES creditos,
 cuota INTEGER NOT NULL, version INTEGER NOT NULL, producto TEXT NOT NULL, segmento TEXT NOT NULL,
 vence TEXT NOT NULL, pendiente INTEGER NOT NULL, carga INTEGER NOT NULL, puntaje REAL NOT NULL,
 margen_ultimo REAL NOT NULL, habitual REAL NOT NULL, reciente REAL NOT NULL, evidencia TEXT NOT NULL,
 pregunta TEXT NOT NULL, baja INTEGER NOT NULL, anteriores INTEGER NOT NULL, evento TEXT, estacional INTEGER NOT NULL,
 PRIMARY KEY(corte,credito,cuota)
);
CREATE INDEX candidatos_asesor ON candidatos(corte,asesor,cliente);
CREATE TABLE revision(corte TEXT NOT NULL REFERENCES semanas, asesor INTEGER NOT NULL, cliente INTEGER NOT NULL, credito INTEGER NOT NULL, cuota INTEGER NOT NULL, motivo TEXT NOT NULL, PRIMARY KEY(corte,credito,cuota));
CREATE INDEX revision_asesor ON revision(corte,asesor);
CREATE TABLE importaciones(id INTEGER PRIMARY KEY, filas INTEGER NOT NULL);

