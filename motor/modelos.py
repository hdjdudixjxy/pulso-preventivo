from collections import Counter
from statistics import median
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from cartera import VARIABLES,etiqueta,ordinal,iso

PERIODOS={
    'entrenamiento':('2023-01-02','2024-12-30'),
    'validacion':('2025-03-10','2025-12-22'),
    'prueba':('2026-03-02','2026-09-21')}
NOMBRES=['Última cuota','Logística','Árboles potenciados','Red neuronal']
REPOSO=28

def muestras(cartera,eventos,periodo):
    ini,fin=map(ordinal,PERIODOS[periodo])
    if fin+63>cartera.fin: raise ValueError('Falta seguimiento completo, incluidos tres días de registro.')
    filas=[]
    for t in range(ini,fin+1,7):
        for r in cartera.corte(t):
            r['episodio'],r['vencimiento_real']=etiqueta(eventos,r)
            filas.append(r)
    return pd.DataFrame(filas)

def candidatos(semilla):
    return {
        'Última cuota':None,
        'Logística':make_pipeline(StandardScaler(),LogisticRegression(max_iter=300)),
        'Árboles potenciados':HistGradientBoostingClassifier(max_iter=90,max_leaf_nodes=15,
            learning_rate=.07,min_samples_leaf=70,l2_regularization=2,early_stopping=False,random_state=semilla),
        'Red neuronal':make_pipeline(StandardScaler(),MLPClassifier(hidden_layer_sizes=(32,16),
            max_iter=150,tol=.0004,n_iter_no_change=10,batch_size=512,alpha=.2,learning_rate_init=.001,random_state=semilla))}

def puntuar(modelo,df):
    if modelo is None:return -df['margen_ultimo'].to_numpy(dtype=float)
    with threadpool_limits(limits=2):
        return modelo.predict_proba(df[VARIABLES])[:,1]

def ordenar(df):
    return df.sort_values(['corte','asesor','puntaje','vence','cliente','credito','cuota'],
        ascending=[True,True,False,True,True,True,True],kind='stable').drop_duplicates(['corte','cliente'])

def seleccionar(ordenadas,cupo,recientes=None):
    anteriores=dict(recientes or {})
    elegidas=[]
    for (t,asesor),grupo in ordenadas.groupby(['corte','asesor'],sort=True):
        candidatas=grupo[grupo.cliente.map(lambda c:t-anteriores.get(c,0)>=REPOSO)].head(cupo)
        anteriores.update({c:t for c in candidatas.cliente})
        elegidas.append(candidatas)
    return pd.concat(elegidas) if elegidas else ordenadas.iloc[:0].copy()

def medicion(cola,universo):
    exitos=cola[cola.episodio!=''].sort_values('corte').drop_duplicates('episodio')
    alcanzables=universo.loc[universo.episodio!='','episodio'].nunique()
    n=len(cola); h=len(exitos)
    return dict(llamadas=n,aciertos=h,falsas=int((cola.episodio=='').sum()),
        repeticiones=int((cola.episodio!='').sum()-h),episodios_alcanzables=int(alcanzables),
        precision=h/n if n else None,cobertura=h/alcanzables if alcanzables else None,
        dias_mediana=float((exitos.vencimiento_real-exitos.corte).median()) if h else None)

def medir(df,modelo,cupo,detalles=False):
    ok=df[df.estado=='evaluable'].copy()
    ok['puntaje']=puntuar(modelo,ok)
    cola=seleccionar(ordenar(ok),cupo)
    m=medicion(cola,df)
    m['precision_media_AP']=float(average_precision_score(ok.episodio!='',ok.puntaje))
    m['semanas']=df.corte.nunique()
    if detalles:
        grupos={
            'Micro':lambda x:x.segmento=='Micro','Pequeña':lambda x:x.segmento=='Pequeña',
            'Estacional':lambda x:x.estacional,'Regular':lambda x:~x.estacional,
            'Menos de un año':lambda x:x.antiguedad_dias<365,'Desde un año':lambda x:x.antiguedad_dias>=365}
        m['grupos']={}
        for nombre,mask in grupos.items():
            univ=df[mask(df)]
            medidas=medicion(cola[mask(cola)],univ)
            medidas['obligaciones_corte']=len(univ)
            medidas['historial_breve']=int((univ.estado=='historial breve').sum())
            medidas['fuente_pendiente']=int((univ.estado=='fuente pendiente').sum())
            m['grupos'][nombre]=medidas
    return m

def entrenar(cartera,semilla,cupo):
    eventos=cartera.resultados()
    train=muestras(cartera,eventos,'entrenamiento')
    train=train[train.estado=='evaluable']
    val=muestras(cartera,eventos,'validacion')
    modelos=candidatos(semilla);valid={}
    for nom,modelo in modelos.items():
        if modelo is not None:
            with threadpool_limits(limits=2): modelo.fit(train[VARIABLES],train.episodio!='')
        valid[nom]=medir(val,modelo,cupo)
    # Fijar ganador ANTES de construir la prueba. En empate gana el más sencillo.
    ganador=max(NOMBRES,key=lambda n:valid[n]['precision'])
    test=muestras(cartera,eventos,'prueba')
    pruebas={n:medir(test,m,cupo,detalles=(n==ganador)) for n,m in modelos.items()}
    red=modelos['Red neuronal'].steps[-1][1]
    informe=dict(periodos=PERIODOS,cupo=cupo,semilla=semilla,seleccion=ganador,iteraciones_red=int(red.n_iter_),
        entrenamiento=dict(filas=len(train),positivas=int((train.episodio!='').sum()),clientes=int(train.cliente.nunique())),
        validacion=valid,prueba=pruebas,estados_prueba={str(k):int(v) for k,v in test.estado.value_counts().items()},
        prevalencia_obligacion_corte=float((test.loc[test.estado=='evaluable','episodio']!='').mean()))
    return dict(nombre=ganador,estimador=modelos[ganador],medianas=train[VARIABLES].median().to_dict(),
                desde=PERIODOS['prueba'][0],variables=VARIABLES),informe

def soles(c):
    return f'S/ {c/100:,.2f}'

def explicar(artefacto,cola):
    """Evidencia numérica y sensibilidad local por grupo, calculada sin etiquetas."""
    if cola.empty:return cola
    cola=cola.copy()
    grupos={
        'margen':['margen_ultimo','margen_reciente','cambio_margen','variabilidad'],
        'historial':['fraccionadas','tardias_previas','demora_registro','cuotas_previas'],
        'calendario':['dias_vencer','carga_7','creditos_activos','fraccion_cubierta'],
        'temporada':['temporada_baja']}
    diferencias={}
    for nombre,cols in grupos.items():
        ref=cola.copy()
        for col in cols: ref[col]=artefacto['medianas'][col]
        diferencias[nombre]=cola.puntaje.to_numpy()-puntuar(artefacto['estimador'],ref)
    razones=[];evidencias=[];preguntas=[]
    for i,r in enumerate(cola.itertuples()):
        orden=sorted(grupos,key=lambda g:-diferencias[g][i])
        mensajes={
            'margen':f'Margen habitual {r.margen_habitual:g} d ({iso(r.previa_desde)} a {iso(r.previa_hasta)}); últimas dos cuotas {r.margen_reciente:g} d. Último vencimiento {iso(r.ultimo_vence)}, cubierto {iso(r.ultimo_pago)}.',
            'historial':f'{round(r.fraccionadas*4)} de 4 cuotas con abonos fraccionados y {round(r.tardias_previas*4)} de 4 cubiertas tras vencer; demora máxima de registro {int(r.demora_registro)} d.',
            'calendario':f'{soles(r.carga_cent)} pendientes en los próximos 7 días. Cuota {r.cuota} del crédito {r.credito}: {soles(r.pendiente_cent)} pendientes al {iso(r.vence)}.',
            'temporada':('El vencimiento cae en temporada baja declarada.' if r.temporada_baja else 'El vencimiento queda fuera de una temporada baja declarada.')}
        razones.append(', '.join(g for g in orden[:2] if diferencias[g][i]>1e-9) or 'Sin aumento frente a la referencia')
        evidencias.append(' | '.join(mensajes[g] for g in orden[:2]))
        preguntas.append('¿La fecha prevista para cobrar sus ventas coincide con sus próximas cuotas?')
    cola['factores_que_suben_el_puntaje']=razones;cola['evidencia']=evidencias;cola['pregunta_sugerida']=preguntas
    return cola
