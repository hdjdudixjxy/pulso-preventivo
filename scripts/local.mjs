import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';
import worker from '../dist/server/index.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const file=process.argv[2]||'.salidas/web.sqlite';
await fs.access(file);
const sql=new DatabaseSync(file);
sql.exec('PRAGMA foreign_keys=ON');
class Statement {
  constructor(query,params=[]){this.statement=sql.prepare(query);this.params=params;}
  bind(...params){this.params=params;return this;}
  first(){return this.statement.get(...this.params)??null;}
  all(){return {results:this.statement.all(...this.params)};}
  run(){return this.statement.run(...this.params);}
}
const db={
  prepare(query){return new Statement(query);},
  batch(statements){sql.exec('BEGIN');try{const out=statements.map(s=>s.statement.columns().length?s.all():s.run());sql.exec('COMMIT');return out;}catch(e){sql.exec('ROLLBACK');throw e;}}
};
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.pdf':'application/pdf'};
const server=http.createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,'http://127.0.0.1:4173');
    if(url.pathname.startsWith('/api/')){
      const chunks=[];for await(const chunk of req)chunks.push(chunk);
      const request=new Request(url,{method:req.method,headers:req.headers,...(chunks.length?{body:Buffer.concat(chunks)}:{})});
      const reply=await worker.fetch(request,{DB:db,LOCAL_PREVIEW:'1'});
      res.writeHead(reply.status,Object.fromEntries(reply.headers));res.end(Buffer.from(await reply.arrayBuffer()));return;
    }
    const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
    if(!['index.html','app.js','estilos.css','marca.png','simbolo.png','manual.pdf'].includes(name)){res.writeHead(404);res.end();return;}
    const content=await fs.readFile(path.join(root,'docs',name));
    res.writeHead(200,{'content-type':mime[path.extname(name)]});res.end(content);
  }catch{res.writeHead(500);res.end('Error al servir la demo local.');}
});
server.listen(4173,'127.0.0.1',()=>console.log('http://127.0.0.1:4173'));

