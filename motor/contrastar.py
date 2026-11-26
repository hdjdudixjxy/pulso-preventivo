"""Auditar ejemplos de prueba y aplicar el modelo congelado a otra cartera ficticia."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import joblib
import pandas as pd
from cartera import Cartera,iso
from modelos import muestras,medir,medicion,ordenar,puntuar,seleccionar,explicar
from simular import crear

def casos(cartera,modelo,cupo):
    df=muestras(cartera,cartera.resultados(),'prueba')
    ok=df[df.estado=='evaluable'].copy()
    ok['puntaje']=puntuar(modelo['estimador'],ok)
    cola=seleccionar(ordenar(ok),cupo)
    detectados=set(cola.episodio)-{''}
    universos=[
        ('Acierto',cola[(cola.episodio!='') & (cola.tardias_previas==0)]),
        ('Acierto con menor margen y aviso de una semana',cola[(cola.episodio!='') & (cola.tardias_previas==0)
            & (cola.cambio_margen>0) & (cola.vencimiento_real-cola.corte>=7)]),
        ('Falsa alarma estacional',cola[(cola.episodio=='') & cola.estacional]),
        ('Episodio omitido',ok[(ok.episodio!='') & ~ok.episodio.isin(detectados)])]
    ejemplos=[]
    for tipo,grupo in universos:
        if grupo.empty:continue
        # El primer caso cronológico que cumple el criterio, sin escoger el puntaje más vistoso.
        ejemplo=grupo.sort_values(['corte','cliente','credito','cuota']).head(1).copy()
        e=explicar(modelo,ejemplo).iloc[0]
        ejemplos.append(dict(tipo=tipo,corte=iso(e.corte),cliente=int(e.cliente),asesor=int(e.asesor),
            credito=int(e.credito),cuota=int(e.cuota),vencimiento_conocido=iso(e.vence),
            importe_pendiente_soles=e.pendiente_cent/100,segmento=e.segmento,
            puntaje=round(e.puntaje,5),evidencia_al_corte=e.evidencia,
            fecha_del_dia_31=iso(e.vencimiento_real+31) if e.episodio else '',
            dias_al_vencimiento_real=int(e.vencimiento_real-e.corte) if e.episodio else None))
    historicos={}
    for nombre,condicion in [('Cuatro últimas cuotas al día',lambda d:d.tardias_previas==0),
            ('Alguna de las cuatro últimas cuotas tardía',lambda d:d.tardias_previas>0),
            ('Cronograma original',lambda d:d.version==1),('Cronograma modificado',lambda d:d.version>1)]:
        historicos[nombre]=medicion(cola[condicion(cola)],ok[condicion(ok)])
    politica={}
    elegibles=ok[ok.dias_vencer>=7].copy()
    for nombre,estimador in [('regla',None),('modelo',modelo['estimador'])]:
        elegibles['puntaje']=puntuar(estimador,elegibles)
        revisiones=seleccionar(ordenar(elegibles),cupo)
        # Mantener todos los episodios originales en el denominador, incluso los que excluiría el filtro.
        politica[nombre]=medicion(revisiones,df)
        politica[nombre]['cuatro_ultimas_al_dia']=medicion(revisiones[revisiones.tardias_previas==0],ok[ok.tardias_previas==0])
    return pd.DataFrame(ejemplos),historicos,politica

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir',type=Path,default=Path(__file__).resolve().parent/'ensayo')
    parser.add_argument('--semilla',type=int,default=1937)
    args=parser.parse_args()
    referencia=json.loads((args.dir/'resultados.json').read_text(encoding='utf8'))
    if args.semilla==referencia['semilla']:raise ValueError('Use otra semilla para la cartera de contraste.')
    modelo=joblib.load(args.dir/'modelo.joblib')
    cupo=referencia['cupo']
    with closing(sqlite3.connect(args.dir/'cartera.sqlite')) as db:
        ejemplos,historicos,politica=casos(Cartera(db),modelo,cupo)
        ejemplos.to_csv(args.dir/'casos_verificados.csv',index=False,encoding='utf-8-sig')
    with closing(sqlite3.connect(':memory:')) as db:
        crear(db,referencia['base']['clientes'],args.semilla)
        cartera=Cartera(db)
        prueba=muestras(cartera,cartera.resultados(),'prueba')
    datos=dict(semilla=args.semilla,modelo_congelado=modelo['nombre'],clientes=referencia['base']['clientes'],
        desglose_cartera_principal_evaluable=historicos,
        escenario_exploratorio_minimo_7_dias_cartera_principal=politica,
        regla=medir(prueba,None,cupo),seleccionado=medir(prueba,modelo['estimador'],cupo))
    (args.dir/'contraste.json').write_text(json.dumps(datos,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf8')
    print(datos)

if __name__=='__main__':main()
