import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const text=f=>fs.readFileSync(path.join(root,f),'utf8');
const list=JSON.parse(text('api/manifest.json'));
const dir=path.join(root,'dist/server');
fs.mkdirSync(dir,{recursive:true});
fs.writeFileSync(path.join(dir,'index.js'),'const MANIFEST='+JSON.stringify(list)+';\n'+text('api/worker.mjs'));

