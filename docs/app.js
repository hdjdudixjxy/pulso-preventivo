const service = location.hostname==='localhost' || location.hostname==='127.0.0.1' ? location.origin : 'https://pulso-preventivo-mype.smallcuckoo8.chatgpt.site';
const $=s=>document.querySelector(s);
const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=c=>new Intl.NumberFormat('es-PE',{style:'currency',currency:'PEN'}).format(c/100);
const date=(v,long=false)=>new Intl.DateTimeFormat('es-PE',{day:'numeric',month:long?'long':'short',year:'numeric',timeZone:'UTC'}).format(new Date(v+'T00:00:00Z'));
const icons={inbox:'M3 14l3-9h12l3 9v5H3z M3 14h5l2 3h4l2-3h5',checks:'M4 7l2 2 4-5 M12 7h8 M4 16l2 2 4-5 M12 16h8',review:'M11 3H5v18h14v-7 M14 5a3 3 0 1 0 6 0 3 3 0 1 0-6 0 M19 8l3 3 M8 12h4 M8 16h6',chart:'M3 3v17h18 M7 16v-4 M12 16V7 M17 16v-6',book:'M12 6c-3-2-6-2-10-1v14c4-1 7-1 10 1 3-2 6-2 10-1V5c-4-1-7-1-10 1z M12 6v14',key:'M3 8a5 5 0 1 0 10 0 5 5 0 0 0-10 0 M12 11l8 8v2h-4v-3h-3v-3',calendar:'M4 6h16v15H4z M4 10h16 M8 3v5 M16 3v5',people:'M5 19v-2c0-4 10-4 10 0v2 M7 7a3 3 0 1 0 6 0 3 3 0 0 0-6 0 M16 12c4 0 5 2 5 5',clock:'M2 12a10 10 0 1 0 20 0 10 10 0 0 0-20 0 M12 6v6l4 2'};
const icon=n=>'<svg class="ico" aria-hidden="true" viewBox="0 0 24 24"><path d="'+icons[n]+'"/></svg>';
document.querySelectorAll('[data-icon]').forEach(i=>i.outerHTML=icon(i.dataset.icon));
const names={bandeja:['Bandeja semanal','Elige a quién contactar antes del próximo vencimiento.'],gestiones:['Gestiones','Consulta las decisiones guardadas en este espacio de demostración.'],revision:['Revisión de datos','Revisa qué información falta para evaluar cada obligación.'],ensayo:['Evaluación del modelo','Resultados del ensayo con la cartera ficticia y casos para contrastarlos.']};
const labels={contactado:'Contactado',observar:'Observar una cuota',cerrar:'Alerta cerrada'};
let view='bandeja', revision=0, caseRev=0, data=null, init=null, active=null;
const fresh=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),x=>x.toString(16).padStart(2,'0')).join('');
const storage='pulso.espacio.v1';
let space=fresh();
try{const value=localStorage.getItem(storage); if(/^[a-f0-9]{32}$/.test(value||''))space=value;localStorage.setItem(storage,space);}catch{}
const filters=()=>({corte:$('#corte').value,asesor:$('#asesor').value,cupo:$('#cupo').value,metodo:$('#metodo').value});
async function api(path,params={},body) {
  const url=new URL('/api/'+path,service);
  Object.entries(params).forEach(([k,v])=>url.searchParams.set(k,v));
  const res=await fetch(url,{headers:{'X-Pulso-Espacio':space,...(body?{'Content-Type':'application/json'}:{})},method:body?'POST':'GET',body:body?JSON.stringify(body):undefined,cache:'no-store'});
  let reply;try{reply=await res.json()}catch{throw Error('El servicio de cartera no está disponible.')}
  if(!res.ok)throw Error(reply.error||'La consulta falló. Intenta nuevamente.');
  return reply;
}
const opt=(v,t)=>'<option value="'+safe(v)+'">'+safe(t)+'</option>';
const card=(title,n,detail,glyph,lead=false)=>`<div class="stat ${lead?'lead':''}">${icon(glyph)}<span>${title}</span><strong>${n}</strong><small>${detail}</small></div>`;
const panel=(title,subtitle,body)=>`<section class="panel"><div class="panelhead"><div><h2>${title}</h2>${subtitle?'<p>'+subtitle+'</p>':''}</div></div>${body}</section>`;
const table=(heads,rows)=>'<div class="tablewrap"><table><thead><tr>'+heads.map(h=>'<th scope="col">'+h+'</th>').join('')+'</tr></thead><tbody>'+rows.join('')+'</tbody></table></div>';
const empty=msg=>'<p class="empty">'+msg+'</p>';
function paint(data) {
 const f=filters();
 const alerts=data.alertas, acts=data.gestiones;
 if(view==='gestiones') return panel('Gestiones de la semana',date(f.corte,true),acts.length?table(['Cliente','Decisión','Seguimiento','Nota'],acts.map(a=>`<tr><td>Cliente ${a.cliente}<small>Crédito ${a.credito} · Cuota ${a.cuota}</small></td><td>${labels[a.accion]}</td><td>${a.seguimiento?date(a.seguimiento):'Sin fecha'}</td><td class="notes">${safe(a.nota)}</td></tr>`)):empty('Todavía no se ha registrado una gestión para este asesor y esta semana.'));
 const soon=alerts.filter(a=>(Date.parse(a.vence)-Date.parse(f.corte))/86400000<=7).length;
 const summary='<div class="summary">'+card('Clientes priorizados',alerts.length,'Cupo de '+f.cupo+' por asesor','people',true)+card('Gestiones registradas',acts.length,'En este espacio y semana','checks')+card('Vencen en 7 días',soon,'Entre los casos de la bandeja','clock')+'</div>';
 const list=alerts.map((a,i)=>`<tr><td><span class="priority ${i<3?'top':''}">${i+1}</span></td><td><strong>Cliente ${a.cliente}</strong><small>${safe(a.segmento)} · ${safe(a.producto)}</small></td><td>${date(a.vence)}<small>Cuota ${a.cuota}</small></td><td>${money(a.pendiente)}</td><td>${a.accion?'<span class="badge">'+labels[a.accion]+'</span>':'Pendiente'}</td><td><button class="linkbtn" data-case="${a.credito},${a.cuota}" aria-label="Ver expediente del cliente ${a.cliente}">Ver expediente</button></td></tr>`);
 return summary+panel('Clientes por contactar',f.metodo==='modelo'?'Ordenados por el puntaje del modelo. Todos están al día al corte.':'Ordenados por el margen de su última cuota pagada. Todos están al día al corte.',list.length?table(['Orden','Cliente','Vencimiento','Pendiente','Gestión','Expediente'],list):empty('No hay clientes elegibles para este corte y asesor.'));
}
function evaluation(){
 const bar=(n,v)=>`<div class="measure"><span>${n}</span><div class="track"><span style="width:${v/200*100}%"></span></div><strong>${v}</strong></div>`;
 return '<div class="summary">'+card('Episodios anticipados','186','De 466 episodios alcanzables','chart',true)+card('Anticipación mediana','14 días','Entre los aciertos del modelo','clock')+card('Contactos simulados','1.150','Mismo cupo para cada método','people')+'</div>'+
 panel('Aciertos con el mismo cupo','30 semanas de prueba · 2 de marzo al 21 de septiembre de 2026','<div class="block">'+bar('Modelo Pulso',186)+bar('Red neuronal',176)+bar('Regresión logística',156)+bar('Regla de última cuota',156)+'<p>El modelo de árboles potenciados obtuvo 30 aciertos adicionales frente a la regla. De sus 1.150 revisiones, 962 fueron falsas alertas y 2 repitieron un episodio. La regla anticipó sus aciertos con una mediana de 16 días.</p></div>')+
 '<div class="cols sectionspace">'+panel('¿Por qué MYPE?','Caja Trujillo · septiembre de 2026','<div class="block"><p>Micro y pequeña empresa concentraron el <strong>77,49 %</strong> del saldo de créditos directos y el <strong>82,91 %</strong> de la cartera atrasada. En el ensayo, microempresa obtuvo 97 aciertos en 556 revisiones y pequeña empresa, 89 en 594.</p><a href="https://intranet2.sbs.gob.pe/estadistica/financiera/2026/Setiembre/C-1228-se2026.XLS">SBS · Créditos directos por tipo y situación, C-1228</a></div>')+
 panel('Contrasta tres expedientes','Abre la evidencia y luego consulta el desenlace.','<div class="block"><button class="linkbtn" data-example="2026-03-23,2,1826,9">Cliente 497 · Acierto temprano</button><br><button class="linkbtn" data-example="2026-03-02,1,669,15">Cliente 182 · Falsa alerta estacional</button><br><button class="linkbtn" data-example="2026-03-02,1,87,6">Cliente 24 · Episodio omitido</button></div>')+'</div>'+
 '<div class="strip">'+icon('book')+'<p>El ensayo mide priorización sobre datos sintéticos. Un piloto con asesores tendría que comprobar la utilidad del contacto y su efecto sobre la cartera. <a href="manual.pdf" target="_blank" rel="noopener">Leer el fundamento y el manual.</a></p></div>';
}
async function render(){
 const seq=++revision;
 $('#status').textContent='';$('#title').textContent=names[view][0];$('#desc').textContent=names[view][1];
 for(const btn of document.querySelectorAll('[data-view]'))btn.setAttribute('aria-current',btn.dataset.view===view?'page':'false');
 $('#filters').hidden=view==='ensayo';$('#datebox').innerHTML=init?icon('calendar')+'Corte del '+date($('#corte').value):'';
 $('#content').setAttribute('aria-busy','true');$('#content').innerHTML='';
 try{
  if(view==='ensayo'){$('#content').innerHTML=evaluation();return;}
  if(!init)return;
  if(view==='revision'){
   const list=await api('revision',filters());if(seq!==revision)return;
   $('#content').innerHTML=panel('Obligaciones en revisión',list.length+' obligaciones · Historial mínimo de cuatro cuotas cubiertas',list.length?table(['Cliente','Crédito','Cuota','Motivo'],list.map(r=>`<tr><td>Cliente ${r.cliente}</td><td>${r.credito}</td><td>${r.cuota}</td><td>${safe(r.motivo)}</td></tr>`)):empty('Todas las obligaciones consideradas tienen información suficiente.'));
  }else{
   const result=await api('cola',filters());if(seq!==revision)return;data=result;$('#content').innerHTML=paint(result);
  }
 }catch(e){if(seq===revision) $('#status').textContent='No se pudo cargar la cartera. '+e.message;}finally{if(seq===revision)$('#content').setAttribute('aria-busy','false');}
}
function caseHTML({caso:a,historia,gestion},example){
 const margin=x=>(x>0?'+':'')+x+' d';
 const his=historia.map(r=>`<tr><td>${r.numero}</td><td>${date(r.vence)}</td><td>${date(r.cubierta)}</td><td>${margin((Date.parse(r.vence)-Date.parse(r.cubierta))/86400000)}</td><td>${r.abonos}</td></tr>`);
 const form=gestion?`<div class="strip"><p><strong>${labels[gestion.accion]}</strong><br>${safe(gestion.nota)}${gestion.seguimiento?'<br>Seguimiento el '+date(gestion.seguimiento):''}</p></div>`:example?'':`<form id="decision"><h3>Registrar una gestión</h3><div class="formgrid"><label>Decisión<select name="accion"><option value="contactado">Contactado</option><option value="observar">Observar una cuota</option><option value="cerrar">Cerrar alerta</option></select></label><label>Seguimiento opcional<input name="seguimiento" type="date" min="${a.corte}"></label><label class="wide">Nota de la conversación ficticia<textarea name="nota" rows="2" required maxlength="300" placeholder="Ej. Acordamos revisar la próxima cuota."></textarea></label></div><div class="actions"><button class="primary" type="submit">Guardar gestión</button></div></form>`;
 return `<p class="path">${safe(a.producto)} · ${safe(a.segmento)} empresa · ${safe(a.sector)} · Corte del ${date(a.corte)}</p><div class="detailsum"><div><small>Próximo vencimiento</small><strong>${date(a.vence)}</strong></div><div><small>Importe pendiente</small><strong>${money(a.pendiente)}</strong></div><div><small>Crédito / cuota</small><strong>${a.credito} / ${a.cuota}</strong></div></div>
 <h3>Evidencia al corte</h3><ul class="evidence">${a.evidencia.split(' | ').map(t=>'<li>'+safe(t)+'</li>').join('')}</ul><p class="historyhint">Cronograma v${a.version}. Margen habitual ${margin(a.habitual)} · Últimas dos cuotas ${margin(a.reciente)}.</p>
 <details><summary>Historial de cuotas cubiertas (${historia.length})</summary><div class="hist">${table(['Cuota','Vencimiento','Pago efectivo','Margen','Abonos'],his)}</div><p class="historyhint">Un margen positivo indica días de adelanto. Solo se incluyen pagos registrados a la fecha del corte.</p></details>
 <h3>Pregunta para el cliente</h3><p class="question">${safe(a.pregunta)}</p>${form}<p id="detailMsg" role="status"></p><hr><div class="actions"><button class="light" id="outcome">Ver desenlace a 60 días</button></div><div id="result" role="status"></div>`;
}
async function openCase(params,example=false){
 const n=++caseRev;active={params,example};$('#detailTitle').textContent='Expediente del cliente';$('#detailBody').textContent='Consultando…';
 if(!$('#detail').open)$('#detail').showModal();
 try{const d=await api('expediente',params);if(n!==caseRev)return;$('#detailTitle').textContent='Cliente '+d.caso.cliente;$('#detailBody').innerHTML=caseHTML(d,example);}
 catch(e){if(n===caseRev)$('#detailBody').textContent=e.message;}
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.view){view=b.dataset.view;await render();}
 if(b.hasAttribute('data-close'))b.closest('dialog').close();
 if(b.dataset.case){const [credito,cuota]=b.dataset.case.split(',');await openCase({...filters(),credito,cuota});}
 if(b.dataset.example){const [corte,asesor,credito,cuota]=b.dataset.example.split(',');await openCase({corte,asesor,credito,cuota,cupo:10,metodo:'modelo'},true);}
 if(b.id==='outcome'){b.disabled=true;const seq=caseRev;try{const r=await api('resultado',active.params);if(seq!==caseRev)return;
 $('#result').innerHTML='<p class="outcome">'+(r.completo?(r.evento?'La cuota llegó a 31 días de atraso el '+date(r.evento)+'.':'La cuota no alcanzó 31 días de atraso dentro de la ventana.')+' Seguimiento hasta el '+date(r.fin)+'.':'Seguimiento incompleto. La cartera llega al '+date(r.hasta)+' y la ventana termina el '+date(r.fin)+'.')+'</p>';}catch(err){if(seq===caseRev)$('#result').textContent=err.message;}finally{b.disabled=false;}}
});
document.addEventListener('submit',async e=>{
 if(e.target.id!=='decision')return;e.preventDefault();const form=e.target,b=form.querySelector('button'),seq=caseRev;
 b.disabled=true;
 try{await api('gestion',active.params,Object.fromEntries(new FormData(form)));if(seq===caseRev){await openCase(active.params);$('#detailMsg').textContent='Gestión guardada en la nube.';}await render();}
 catch(err){if(seq===caseRev)$('#detailMsg').textContent=err.message;b.disabled=false;}
});
$('#detail').addEventListener('close',()=>{caseRev++;active=null;});
$('#team').onclick=()=>{$('#spacecode').value=space;$('#spaceMsg').textContent='';$('#space').showModal();};
$('#copycode').onclick=async()=>{try{await navigator.clipboard.writeText(space);$('#spaceMsg').textContent='Código copiado.';}catch{$('#spacecode').select();$('#spaceMsg').textContent='Copia el código seleccionado.';}};
$('#usespace').onclick=async()=>{const key=$('#spacecode').value.trim().toLowerCase();if(!/^[a-f0-9]{32}$/.test(key)){$('#spaceMsg').textContent='El código debe tener 32 caracteres hexadecimales.';return;}space=key;try{localStorage.setItem(storage,key);}catch{}$('#space').close();await render();};
async function boot(){
 try{init=await api('inicio');if(!init.semanas.length)throw Error('La cartera todavía está cargando.');
 $('#asesor').innerHTML=init.asesores.map(a=>opt(a.id,'Asesor '+a.id+' · '+a.agencia)).join('');
 $('#corte').innerHTML=init.semanas.map(c=>opt(c,date(c,true))).join('');
 $('#cupo').innerHTML=Array.from({length:10},(_,i)=>opt(i+1,i+1)).join('');$('#cupo').value=10;
 $('#filters').addEventListener('change',render);await render();
 }catch(e){$('#status').textContent='No se pudo abrir la cartera. '+e.message;$('#content').innerHTML='<button class="light" id="retry">Volver a conectar</button>';$('#retry').onclick=boot;}
}
boot();

