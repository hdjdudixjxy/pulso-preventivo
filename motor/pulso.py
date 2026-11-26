"""Motor local de Pulso Preventivo, sin conexiones a sistemas de Caja Trujillo."""
import argparse
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import joblib
import pandas as pd
from cartera import Cartera,iso,ordinal
from modelos import entrenar,explicar,ordenar,puntuar,seleccionar,REPOSO
from simular import crear

BASE=Path(__file__).resolve().parent
DEMO='2026-11-23'
COLUMNAS=['corte','asesor','cliente','credito','cuota','version','producto','segmento','vence',
    'pendiente_cent','carga_cent','puntaje','factores_que_suben_el_puntaje','evidencia','pregunta_sugerida']

def semanal(db,modelo,fecha,cupo,min_dias=1):
    corte=ordinal(fecha)
    if fecha<modelo['desde']: raise ValueError('El modelo se puede aplicar desde '+modelo['desde'])
    if cupo<1:raise ValueError('El cupo debe ser positivo')
    if not 1<=min_dias<=29:raise ValueError('La anticipación mínima debe estar entre 1 y 29 días.')
    filas=pd.DataFrame(Cartera(db).corte(corte))
    if filas.empty:return pd.DataFrame(columns=COLUMNAS),pd.DataFrame()
    pendientes=filas[filas.estado!='evaluable'][['corte','asesor','cliente','credito','cuota','estado']].copy()
    pendientes['corte']=pendientes.corte.map(iso)
    ok=filas[(filas.estado=='evaluable') & (filas.dias_vencer>=min_dias)].copy()
    if ok.empty: return pd.DataFrame(columns=COLUMNAS),pendientes
    ok['puntaje']=puntuar(modelo['estimador'],ok)
    ultimos={c:ordinal(f) for c,f in db.execute('SELECT cliente_id,MAX(fecha_accion) FROM gestiones WHERE fecha_accion<=? GROUP BY cliente_id',(fecha,))}
    cola=explicar(modelo,seleccionar(ordenar(ok),cupo,ultimos))[COLUMNAS].copy()
    for col in ('corte','vence'):cola[col]=cola[col].map(iso)
    return cola,pendientes

def escribir_cola(carpeta,fecha,cola,pendientes):
    cola.to_csv(carpeta/f'alertas_{fecha}.csv',index=False,encoding='utf-8-sig')
    pendientes.to_csv(carpeta/f'revision_datos_{fecha}.csv',index=False,encoding='utf-8-sig')

def demo(args):
    if args.clientes<250 or args.cupo<1:raise ValueError('Use al menos 250 clientes y un cupo positivo para el ensayo.')
    destino=args.dir.resolve()
    if destino.exists():raise ValueError('Ya existe el ensayo. Use cola o indique otro directorio con --dir.')
    destino.parent.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(dir=destino.parent) as scratch:
        datos=Path(scratch)/'ensayo';datos.mkdir()
        with closing(sqlite3.connect(datos/'cartera.sqlite')) as db:
            crear(db,args.clientes,args.semilla)
            totales={tabla:db.execute('SELECT COUNT(*) FROM '+tabla).fetchone()[0]
                     for tabla in ('clientes','asesores','productos','creditos','cronogramas','cuotas','abonos','incidencias_fuente')}
            print('Base generada:',totales,flush=True)
            modelo,informe=entrenar(Cartera(db),args.semilla,args.cupo)
            informe['base']=totales
            joblib.dump(modelo,datos/'modelo.joblib',compress=3)
            cola,pendientes=semanal(db,modelo,DEMO,args.cupo)
            escribir_cola(datos,DEMO,cola,pendientes)
        (datos/'resultados.json').write_text(json.dumps(informe,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf8')
        datos.rename(destino)
    print('Elegido en validación:',informe['seleccion'])
    for n,m in informe['prueba'].items():print(n,m['aciertos'],m['llamadas'],m['precision'],m['dias_mediana'])

def operar(args):
    if not (args.dir/'cartera.sqlite').is_file():raise ValueError('Falta cartera.sqlite en el directorio del ensayo.')
    with closing(sqlite3.connect(args.dir/'cartera.sqlite')) as db:
        db.execute('PRAGMA foreign_keys=ON')
        if args.comando=='cola':
            modelo=joblib.load(args.dir/'modelo.joblib')  # artefacto local creado por demo
            cola,pendientes=semanal(db,modelo,args.fecha,args.cupo,args.min_dias)
            sufijo='' if (args.cupo,args.min_dias)==(10,1) else f'_k{args.cupo}_d{args.min_dias}'
            escribir_cola(args.dir,args.fecha+sufijo,cola,pendientes)
            print(cola[['asesor','cliente','credito','vence','evidencia']].to_string(index=False,max_rows=8))
            print('Alertas:',len(cola),'filas de revisión de datos:',len(pendientes))
        else:
            dia=ordinal(args.fecha); corte=ordinal(args.corte)
            fin=ordinal(db.execute("SELECT valor FROM metadata WHERE clave='observado_hasta'").fetchone()[0])
            if not corte<=dia<=fin or (args.seguimiento and ordinal(args.seguimiento)<dia):
                raise ValueError('Revise la fecha de corte, de gestión y de seguimiento.')
            # Verificar el expediente y la asignación del asesor en el corte registrado.
            row=db.execute('''SELECT l.cliente_id,c.asesor_id FROM creditos l JOIN clientes c ON c.id=l.cliente_id
                WHERE l.id=? AND EXISTS (SELECT 1 FROM cronogramas v JOIN cuotas q ON v.id=q.cronograma_id
                WHERE v.credito_id=l.id AND q.numero=? AND v.registrado<=? AND v.vigente_desde<=?)''',
                (args.credito,args.cuota,args.corte,args.corte)).fetchone()
            if not row or row[1]!=args.asesor: raise ValueError('No se encontró esa obligación asignada al asesor.')
            with db:
                db.execute('INSERT INTO gestiones(cliente_id,credito_id,numero,corte,fecha_accion,accion,seguimiento,nota,asesor_id) VALUES (?,?,?,?,?,?,?,?,?)',
                    (row[0],args.credito,args.cuota,args.corte,args.fecha,args.accion,args.seguimiento,args.nota,args.asesor))
            print('Gestión guardada. En la cola, el cliente queda en pausa durante',REPOSO,'días.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='comando',required=True)
    crear_cmd=subs.add_parser('demo',help='Generar una cartera y repetir el experimento')
    crear_cmd.add_argument('--clientes',type=int,default=1200);crear_cmd.add_argument('--semilla',type=int,default=731)
    cola=subs.add_parser('cola',help='Puntuar un corte histórico');cola.add_argument('--fecha',default=DEMO)
    cola.add_argument('--min-dias',type=int,default=1,help='Días mínimos hasta el vencimiento conocido (1 a 29)')
    accion=subs.add_parser('gestion',help='Registrar una decisión humana en la base ficticia')
    for campo,tipo in [('asesor',int),('credito',int),('cuota',int),('corte',str),('fecha',str),('nota',str)]:
        accion.add_argument('--'+campo,type=tipo,required=True)
    accion.add_argument('--seguimiento');accion.add_argument('--accion',choices=['contactado','observar','cerrar'],required=True)
    for p in (crear_cmd,cola,accion):p.add_argument('--dir',type=Path,default=BASE/'ensayo')
    for p in (crear_cmd,cola):p.add_argument('--cupo',type=int,default=10)
    args=parser.parse_args()
    if args.comando=='demo':demo(args)
    else:operar(args)

if __name__=='__main__': main()
