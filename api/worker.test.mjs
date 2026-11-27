// Pruebas del Worker sobre una cartera mínima en SQLite. Ejecutar con: node --test api/
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { d1 } from '../scripts/d1local.mjs';

const lote = gzipSync(Buffer.from(JSON.stringify([['fuente', 'PRUEBA']])));
globalThis.MANIFEST = [{ table: 'metadata', cols: ['clave', 'valor'], n: 1, file: '0000.gz',
  hash: createHash('sha256').update(lote).digest('hex') }];
const { default: worker } = await import('./worker.mjs');

const esquema = fs.readFileSync(new URL('../drizzle/0000_cartera.sql', import.meta.url), 'utf8');
const ESPACIO = 'a'.repeat(32), OTRO = 'b'.repeat(32);
const CORTES = ['2026-03-02', '2026-03-09', '2026-03-16', '2026-04-06'];

function cartera() {
  const db = d1();
  db.sql.exec(esquema);
  const run = (q, ...rows) => { const s = db.sql.prepare(q); rows.forEach(r => s.run(...r)); };
  run('INSERT INTO metadata VALUES (?,?)', ['observado_hasta', '2026-05-10']);
  run('INSERT INTO asesores VALUES (?,?)', [1, 'Trujillo'], [2, 'Chepén']);
  run("INSERT INTO productos VALUES ('Facilito','PEN','mensual',0.2,0.9)", []);
  run("INSERT INTO clientes VALUES (?,?,'La Libertad','comercio',NULL,'2025-01-01')", [1, 1], [2, 1], [3, 1], [4, 2]);
  run("INSERT INTO creditos VALUES (?,?,'Facilito','Micro','2025-12-01',60000,0.3,6)",
    [10, 1], [11, 1], [20, 2], [30, 3], [40, 4]);
  run("INSERT INTO cronogramas VALUES (100,10,1,'2025-12-01','2025-12-01','original')", []);
  run('INSERT INTO cuotas VALUES (100,?,?,?,10000,500)',
    [1, '2025-12-10', '2026-01-10'], [2, '2026-01-10', '2026-02-10'], [3, '2026-02-10', '2026-03-05'], [4, '2026-03-05', '2026-04-10']);
  run('INSERT INTO abonos VALUES (?,10,?,?,?,?,?)',
    [1, 1, '2026-01-08', '2026-01-08', 10500, 'agencia'],
    [2, 2, '2026-02-09', '2026-02-09', 5000, 'agencia'],
    [3, 2, '2026-02-12', '2026-02-12', 5500, 'digital'],
    [4, 3, '2026-03-04', '2026-03-10', 10500, 'digital']); // registrado después del corte del 09/03
  const candidato = db.sql.prepare(`INSERT INTO candidatos VALUES (?,?,?,?,?,1,'Facilito','Micro','2026-04-10',10500,10500,?,?,4,2,
    'Evidencia uno | Evidencia dos','¿Pregunta?',0,4,?,0)`);
  for (const corte of CORTES) {
    db.sql.prepare('INSERT INTO semanas VALUES (?)').run(corte);
    for (const [asesor, cliente, credito, cuota, puntaje, margen, evento] of [
      [1, 1, 10, 4, 0.9, 5, '2026-05-11'], [1, 1, 11, 2, 0.5, -3, null], [1, 2, 20, 1, 0.7, 1, null],
      [1, 3, 30, 1, 0.2, -1, null], [2, 4, 40, 1, 0.8, 0, null]])
      candidato.run(corte, asesor, cliente, credito, cuota, puntaje, margen, evento);
  }
  return db;
}

async function call(db, path, { espacio = ESPACIO, body, origin, env = {} } = {}) {
  const headers = {};
  if (espacio) headers['X-Pulso-Espacio'] = espacio;
  if (origin) headers.Origin = origin;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const req = new Request('https://servicio.test' + path, { method: body === undefined ? 'GET' : 'POST', headers,
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body) });
  const res = await worker.fetch(req, { DB: db, ...env });
  const text = await res.text();
  return { status: res.status, headers: res.headers, data: text ? JSON.parse(text) : null };
}
const cola = async (db, corte, extra = '', espacio) =>
  (await call(db, `/api/cola?corte=${corte}&asesor=1${extra}`, { espacio })).data;
const clientes = r => r.alertas.map(a => a.cliente);
const guardar = (db, corte, credito, cuota, body = { accion: 'contactado', nota: 'Nota ficticia' }, espacio) =>
  call(db, `/api/gestion?corte=${corte}&asesor=1&credito=${credito}&cuota=${cuota}`, { body, espacio });

test('inicio y estado no requieren espacio', async () => {
  const db = cartera();
  const inicio = await call(db, '/api/inicio', { espacio: null });
  assert.equal(inicio.status, 200);
  assert.deepEqual(inicio.data.semanas, [...CORTES].reverse());
  assert.equal(inicio.data.observado, '2026-05-10');
  assert.equal((await call(db, '/api/estado', { espacio: null })).data.lotes, 1);
});

test('las rutas de la bandeja exigen un espacio válido y parámetros correctos', async () => {
  const db = cartera();
  assert.equal((await call(db, '/api/cola?corte=2026-03-02&asesor=1', { espacio: null })).status, 401);
  assert.equal((await call(db, '/api/cola?corte=2026-03-02&asesor=1', { espacio: 'XYZ' })).status, 401);
  for (const q of ['corte=2026-02-30&asesor=1', 'corte=2026-03-02&asesor=9', 'corte=2026-03-02&asesor=1&cupo=11',
    'corte=2026-03-02&asesor=1&metodo=azar'])
    assert.equal((await call(db, '/api/cola?' + q)).status, 400, q);
  assert.equal((await call(db, '/api/otra?corte=2026-03-02&asesor=1')).status, 404);
});

test('la bandeja ordena por método, deja una obligación por cliente y respeta el cupo', async () => {
  const db = cartera();
  const modelo = await cola(db, '2026-03-02');
  assert.deepEqual(clientes(modelo), [1, 2, 3]);
  assert.equal(modelo.alertas[0].credito, 10);
  const regla = await cola(db, '2026-03-02', '&metodo=regla');
  assert.deepEqual(clientes(regla), [1, 3, 2]);
  assert.equal(regla.alertas[0].credito, 11);
  assert.deepEqual(clientes(await cola(db, '2026-03-02', '&cupo=2')), [1, 2]);
});

test('una gestión pausa al cliente 28 días antes y después de su corte, solo en su espacio', async () => {
  const db = cartera();
  assert.deepEqual((await guardar(db, '2026-03-09', 20, 1)).data, { guardado: true });
  const misma = await cola(db, '2026-03-09');
  assert.deepEqual(clientes(misma), [1, 2, 3]);
  assert.equal(misma.alertas.find(a => a.cliente === 2).accion, 'contactado');
  assert.deepEqual(clientes(await cola(db, '2026-03-02')), [1, 3]);
  assert.deepEqual(clientes(await cola(db, '2026-03-16')), [1, 3]);
  assert.deepEqual(clientes(await cola(db, '2026-04-06')), [1, 2, 3]); // a 28 días exactos termina la pausa
  assert.deepEqual(clientes(await cola(db, '2026-03-16', '', OTRO)), [1, 2, 3]);

  for (const corte of ['2026-03-02', '2026-03-16']) {
    const r = await guardar(db, corte, 20, 1);
    assert.equal(r.status, 409);
    assert.match(r.data.error, /pausa de 28 días.*2026-03-09/);
  }
  assert.equal((await guardar(db, '2026-04-06', 20, 1)).status, 200);
  assert.equal((await guardar(db, '2026-03-16', 20, 1, undefined, OTRO)).status, 200);
});

test('no se registra dos veces la misma semana ni una obligación fuera de la bandeja', async () => {
  const db = cartera();
  assert.equal((await guardar(db, '2026-03-02', 10, 4)).status, 200);
  assert.equal((await guardar(db, '2026-03-02', 10, 4, { accion: 'cerrar', nota: 'Otra' })).status, 409);
  assert.equal((await guardar(db, '2026-03-02', 11, 2)).status, 409); // obligación no preferida del cliente
  const gestiones = (await cola(db, '2026-03-02')).gestiones;
  assert.deepEqual(gestiones, [{ cliente: 1, credito: 10, cuota: 4, accion: 'contactado', seguimiento: null, nota: 'Nota ficticia' }]);
});

test('valida la decisión, la nota y la fecha de seguimiento', async () => {
  const db = cartera();
  for (const body of [{ accion: 'llamar', nota: 'x' }, { accion: 'observar', nota: '   ' },
    { accion: 'observar', nota: 'x'.repeat(301) }, { accion: 'observar', nota: 'x', seguimiento: '2026-03-01' },
    { accion: 'observar', nota: 'x', seguimiento: 20260310 }, 'no es json', null])
    assert.equal((await guardar(db, '2026-03-02', 10, 4, body)).status, 400, JSON.stringify(body));
  const ok = await guardar(db, '2026-03-02', 10, 4, { accion: 'observar', nota: ' Revisar ', seguimiento: '2026-03-02' });
  assert.equal(ok.status, 200);
  const exp = await call(db, '/api/expediente?corte=2026-03-02&asesor=1&credito=10&cuota=4');
  assert.deepEqual(exp.data.gestion, { accion: 'observar', nota: 'Revisar', seguimiento: '2026-03-02' });
});

test('el expediente solo usa pagos registrados al corte y oculta el desenlace', async () => {
  const db = cartera();
  const a = (await call(db, '/api/expediente?corte=2026-03-09&asesor=1&credito=10&cuota=4')).data;
  assert.equal(a.caso.evento, undefined);
  assert.equal(a.caso.sector, 'comercio');
  assert.deepEqual(a.historia.map(h => [h.numero, h.cubierta, h.abonos]), [[1, '2026-01-08', 1], [2, '2026-02-12', 2]]);
  const b = (await call(db, '/api/expediente?corte=2026-03-16&asesor=1&credito=10&cuota=4')).data;
  assert.deepEqual(b.historia.map(h => h.numero), [1, 2, 3]);
  assert.equal((await call(db, '/api/expediente?corte=2026-03-09&asesor=2&credito=10&cuota=4')).status, 404);
});

test('el desenlace se muestra solo con 60 días observados', async () => {
  const db = cartera();
  const q = c => `/api/resultado?corte=${c}&asesor=1&credito=10&cuota=4`;
  assert.deepEqual((await call(db, q('2026-03-02'))).data, { completo: true, evento: '2026-05-11', fin: '2026-05-01' });
  assert.deepEqual((await call(db, q('2026-03-16'))).data, { completo: false, hasta: '2026-05-10', fin: '2026-05-15' });
  db.sql.exec("DELETE FROM metadata WHERE clave='observado_hasta'");
  const r = await call(db, q('2026-03-02'));
  assert.equal(r.status, 503);
  assert.match(r.data.error, /observaron/);
});

test('la importación verifica la huella y no duplica lotes', async () => {
  const db = cartera();
  const subir = (i, bytes) => worker.fetch(new Request('https://servicio.test/api/importar/' + i,
    { method: 'POST', body: bytes }), { DB: db });
  assert.equal((await subir(5, lote)).status, 404);
  assert.equal((await subir(0, gzipSync(Buffer.from('[["fuente","OTRA"]]')))).status, 403);
  assert.deepEqual(await (await subir(0, lote)).json(), { filas: 1 });
  assert.deepEqual(await (await subir(0, lote)).json(), { filas: 1, existente: true });
  assert.deepEqual(db.sql.prepare("SELECT valor FROM metadata WHERE clave='fuente'").all().map(r => r.valor), ['PRUEBA']);
});

test('CORS solo para el origen publicado o la vista local', async () => {
  const db = cartera();
  const pages = await call(db, '/api/inicio', { origin: 'https://hdjdudixjxy.github.io' });
  assert.equal(pages.headers.get('Access-Control-Allow-Origin'), 'https://hdjdudixjxy.github.io');
  assert.equal((await call(db, '/api/inicio', { origin: 'https://otro.example' })).headers.get('Access-Control-Allow-Origin'), null);
  assert.equal((await call(db, '/api/inicio', { origin: 'http://localhost:4173' })).headers.get('Access-Control-Allow-Origin'), null);
  const local = await call(db, '/api/inicio', { origin: 'http://localhost:4173', env: { LOCAL_PREVIEW: '1' } });
  assert.equal(local.headers.get('Access-Control-Allow-Origin'), 'http://localhost:4173');
});
