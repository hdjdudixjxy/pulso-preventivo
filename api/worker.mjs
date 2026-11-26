// MANIFEST is injected at build time from the signed-off synthetic dataset.
const allowedOrigin = 'https://hdjdudixjxy.github.io';
const page = allowedOrigin + '/pulso-preventivo/';
const json = (value, status=200) => Response.json(value,{status});
class Failure extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
function check(condition, message, status=400) {
  if (!condition) throw new Failure(status,message);
}
async function digest(bytes) {
  const hash = await crypto.subtle.digest('SHA-256',bytes);
  return Array.from(new Uint8Array(hash), b=>b.toString(16).padStart(2,'0')).join('');
}
async function namespace(request) {
  const key=request.headers.get('X-Pulso-Espacio')||'';
  check(/^[a-f0-9]{32}$/.test(key),'Abre o crea tu espacio de demostración.',401);
  return digest(new TextEncoder().encode(key));
}
function day(s) {
  return /^\d{4}-\d\d-\d\d$/.test(s||'') && !Number.isNaN(Date.parse(s)) && new Date(s).toISOString().slice(0,10)===s;
}
async function seed(request, db, index) {
  const meta = MANIFEST[index];
  check(meta,'Lote desconocido.',404);
  const existing = await db.prepare('SELECT filas FROM importaciones WHERE id=?').bind(index).first();
  if(existing) return json({filas:existing.filas,existente:true});
  check(Number(request.headers.get('content-length')||0)<1000000,'Lote demasiado grande.',413);
  const bytes=await request.arrayBuffer();
  check(bytes.byteLength<1000000 && await digest(bytes)===meta.hash,'Huella de lote incorrecta.',403);
  const rows=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
  const fields=meta.cols.map((_,i)=>"json_extract(value,'$["+i+"]')").join(',');
  const sql='INSERT INTO '+meta.table+' ('+meta.cols.join(',')+') SELECT '+fields+' FROM json_each(?) WHERE NOT EXISTS (SELECT 1 FROM importaciones WHERE id=?)';
  await db.batch([db.prepare(sql).bind(rows,index),db.prepare('INSERT OR IGNORE INTO importaciones VALUES (?,?)').bind(index,meta.n)]);
  return json({filas:meta.n});
}
const ordering={
  modelo:'a.puntaje DESC, a.vence, a.cliente, a.credito, a.cuota',
  regla:'a.margen_ultimo ASC, a.vence, a.cliente, a.credito, a.cuota'
};
function listSql(method) {
  const order=ordering[method];
  return `WITH candidatas AS (
    SELECT a.*, ROW_NUMBER() OVER(PARTITION BY a.cliente ORDER BY ${order}) AS preferida
    FROM candidatos a WHERE a.corte=? AND a.asesor=? AND NOT EXISTS (
      SELECT 1 FROM gestiones g WHERE g.espacio=? AND g.cliente_id=a.cliente
      AND g.fecha_accion<a.corte AND g.fecha_accion>date(a.corte,'-28 days')))
    SELECT a.cliente,a.credito,a.cuota,a.segmento,a.producto,a.vence,a.pendiente,a.habitual,a.reciente,
           a.estacional,g.accion FROM candidatas a LEFT JOIN gestiones g ON g.espacio=? AND g.cliente_id=a.cliente AND g.corte=a.corte
    WHERE a.preferida=1 ORDER BY ${order} LIMIT ?`;
}
function key(params) {
  const corte=params.get('corte'), asesor=Number(params.get('asesor')), cupo=Number(params.get('cupo')||10);
  const metodo=params.get('metodo')||'modelo';
  check(day(corte) && Number.isInteger(asesor) && asesor>=1 && asesor<=4 && Object.hasOwn(ordering,metodo) && Number.isInteger(cupo) && cupo>=1 && cupo<=10,'Revisa el corte, el asesor y el cupo.');
  return {corte,asesor,cupo,metodo};
}
async function route(request, db) {
  const url=new URL(request.url), path=url.pathname, params=url.searchParams;
  if(path==='/') return Response.redirect(page,302);
  const imp=path.match(/^\/api\/importar\/(\d+)$/);
  if(imp && request.method==='POST') return seed(request,db,Number(imp[1]));
  if(path==='/api/estado' && request.method==='GET'){
    const r=await db.prepare(`SELECT (SELECT COUNT(*) FROM importaciones) AS cargados,
      (SELECT COUNT(*) FROM clientes) AS clientes,(SELECT COUNT(*) FROM creditos) AS creditos,
      (SELECT COUNT(*) FROM cronogramas) AS cronogramas,(SELECT COUNT(*) FROM cuotas) AS cuotas,
      (SELECT COUNT(*) FROM abonos) AS abonos,(SELECT COUNT(*) FROM semanas) AS semanas`).first();
    return json({...r,lotes:MANIFEST.length});
  }
  if(path==='/api/inicio' && request.method==='GET'){
    const [weeks,people,finish]=await db.batch([db.prepare('SELECT corte FROM semanas ORDER BY corte DESC'),
      db.prepare('SELECT id,agencia FROM asesores ORDER BY id'),db.prepare("SELECT valor FROM metadata WHERE clave='observado_hasta'")]);
    return json({semanas:weeks.results.map(r=>r.corte),asesores:people.results,observado:finish.results[0]?.valor});
  }
  const espacio=await namespace(request);
  const {corte,asesor,cupo,metodo}=key(params);
  const queue=()=>db.prepare(listSql(metodo)).bind(corte,asesor,espacio,espacio,cupo);
  if(path==='/api/cola' && request.method==='GET'){
    const [alerts,quality,handled]=await db.batch([queue(),
      db.prepare('SELECT motivo,COUNT(*) AS n FROM revision WHERE corte=? AND asesor=? GROUP BY motivo').bind(corte,asesor),
      db.prepare('SELECT cliente_id AS cliente,credito_id AS credito,numero AS cuota,accion,seguimiento,nota FROM gestiones WHERE espacio=? AND corte=? AND asesor_id=? ORDER BY id DESC').bind(espacio,corte,asesor)]);
    return json({alertas:alerts.results,calidad:quality.results,gestiones:handled.results});
  }
  if(path==='/api/revision' && request.method==='GET'){
    return json((await db.prepare('SELECT cliente,credito,cuota,motivo FROM revision WHERE corte=? AND asesor=? ORDER BY cliente,credito,cuota').bind(corte,asesor).all()).results);
  }
  check(['/api/expediente','/api/resultado','/api/gestion'].includes(path),'Ruta desconocida.',404);
  const credito=Number(params.get('credito')),cuota=Number(params.get('cuota'));
  check(Number.isInteger(credito) && Number.isInteger(cuota),'Obligación inválida.');
  const a=await db.prepare(`SELECT a.*, c.sector,c.departamento FROM candidatos a JOIN clientes c ON c.id=a.cliente
    WHERE a.corte=? AND a.asesor=? AND a.credito=? AND a.cuota=?`).bind(corte,asesor,credito,cuota).first();
  check(a,'Expediente fuera de este corte o asesor.',404);
  if(path==='/api/resultado' && request.method==='GET'){
    const fin=await db.prepare("SELECT valor FROM metadata WHERE clave='observado_hasta'").first();
    const end = new Date(Date.parse(corte)+60*86400000).toISOString().slice(0,10);
    return json(end>fin.valor?{completo:false,hasta:fin.valor,fin:end}:{completo:true,evento:a.evento,fin:end});
  }
  if(path==='/api/expediente' && request.method==='GET'){
    delete a.evento;
    const [history,action]=await db.batch([db.prepare(`WITH recuperadas AS (
      SELECT q.numero,q.vence,q.capital_cent+q.interes_cent AS total,b.efectiva,b.registrada,b.importe_cent,
      SUM(b.importe_cent) OVER(PARTITION BY q.numero ORDER BY b.efectiva,b.id) AS acumulado
      FROM cronogramas v JOIN cuotas q ON v.id=q.cronograma_id JOIN abonos b ON b.credito_id=v.credito_id AND b.numero=q.numero
      WHERE v.credito_id=? AND v.version=? AND q.vence<=? AND b.efectiva<=? AND b.registrada<=?)
      SELECT numero,vence,total,MIN(CASE WHEN acumulado>=total THEN efectiva END) AS cubierta,COUNT(*) AS abonos
      FROM recuperadas GROUP BY numero HAVING MAX(acumulado)>=total ORDER BY vence DESC LIMIT 8`).bind(credito,a.version,corte,corte,corte),
      db.prepare('SELECT accion,nota,seguimiento FROM gestiones WHERE espacio=? AND corte=? AND cliente_id=?').bind(espacio,corte,a.cliente)]);
    return json({caso:a,historia:history.results.reverse(),gestion:action.results[0]||null});
  }
  check(path==='/api/gestion' && request.method==='POST','Método no admitido.',405);
  const body=await request.json().catch(()=>null);
  check(body && ['contactado','observar','cerrar'].includes(body.accion),'Elige una decisión.');
  const nota=typeof body.nota==='string'?body.nota.trim():'';
  const seguimiento=body.seguimiento||null;
  check(nota.length>0 && nota.length<=300 && (!seguimiento || (day(seguimiento) && seguimiento>=corte)),'Revisa la nota (1 a 300 caracteres) y la fecha de seguimiento.');
  const list=(await queue().all()).results;
  check(list.some(x=>x.credito===credito && x.cuota===cuota),'La obligación ya no está en la bandeja.',409);
  await db.prepare(`INSERT INTO gestiones(espacio,cliente_id,credito_id,numero,corte,fecha_accion,accion,seguimiento,nota,asesor_id)
    SELECT ?,?,?,?,?,?,?,?,?,? WHERE (SELECT COUNT(*) FROM gestiones WHERE espacio=? AND corte=? AND asesor_id=?)<10
    AND NOT EXISTS(SELECT 1 FROM gestiones WHERE espacio=? AND cliente_id=?
      AND fecha_accion>date(?,'-28 days') AND fecha_accion<date(?,'+28 days'))
    ON CONFLICT(espacio,corte,cliente_id) DO NOTHING`)
    .bind(espacio,a.cliente,credito,cuota,corte,corte,body.accion,seguimiento,nota,asesor,espacio,corte,asesor,espacio,a.cliente,corte,corte).run();
  const saved=await db.prepare('SELECT accion,seguimiento,nota,credito_id,numero FROM gestiones WHERE espacio=? AND corte=? AND cliente_id=?').bind(espacio,corte,a.cliente).first();
  check(saved && saved.accion===body.accion && saved.nota===nota && saved.seguimiento===seguimiento && saved.credito_id===credito && saved.numero===cuota,'La bandeja cambió o ya existe una gestión. Actualiza la vista.',409);
  return json({guardado:true});
}
export default {async fetch(request,env) {
  const origin=request.headers.get('Origin');
  const local=env.LOCAL_PREVIEW==='1' && /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin||'');
  const cors={'Vary':'Origin','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
  if(origin===allowedOrigin || local) {
    cors['Access-Control-Allow-Origin']=origin;
    cors['Access-Control-Allow-Headers']='Content-Type, X-Pulso-Espacio';
    cors['Access-Control-Allow-Methods']='GET, POST, OPTIONS';
  }
  let res;
  try {
    res=request.method==='OPTIONS'?new Response(null,{status:204}):await route(request,env.DB);
  } catch(e) {
    if(!(e instanceof Failure)) console.error('Error de servicio',e.message);
    res=json({error:e instanceof Failure?e.message:'El servicio no pudo completar la consulta.'},e.status||500);
  }
  const out=new Response(res.body,res);
  Object.entries(cors).forEach(([k,v])=>out.headers.set(k,v));
  return out;
}};

