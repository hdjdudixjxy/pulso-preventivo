"""Vista semanal a fin del día. Los resultados futuros se reconstruyen en un paso separado."""
from collections import defaultdict
from dataclasses import dataclass,field
from datetime import date
from statistics import median

def ordinal(s):
    return date.fromisoformat(s).toordinal()
def iso(n):
    return date.fromordinal(int(n)).isoformat()

VARIABLES=['margen_ultimo','margen_reciente','cambio_margen','variabilidad','fraccionadas',
           'tardias_previas','demora_registro','carga_7','dias_vencer','fraccion_cubierta',
           'creditos_activos','cuotas_previas','temporada_baja']

@dataclass
class Credito:
    id:int
    cliente:int
    asesor:int
    agencia:str
    segmento:str
    producto:str
    inicio:int
    mes_bajo:int|None
    versiones:list=field(default_factory=list)
    pagos:dict=field(default_factory=lambda:defaultdict(list))
    cerrado:int|None=None

def version_en(credito,corte):
    return next((v for v in reversed(credito.versiones) if max(v[0],v[1])<=corte),None)

def cubierto(pagos,total,corte):
    """Devuelve importe, día de cobertura efectiva, partes y demora de registro a la fecha."""
    cantidad=0; acumulado=0; fecha=None; demora=0
    for efectiva,registro,importe in pagos:  # orden de fecha efectiva
        if max(efectiva,registro)>corte: continue
        acumulado+=importe; cantidad+=1; demora=max(demora,registro-efectiva)
        if fecha is None and acumulado>=total: fecha=efectiva
    return acumulado,fecha,cantidad,demora

class Cartera:
    def __init__(self,db):
        self.fin=ordinal(db.execute("SELECT valor FROM metadata WHERE clave='observado_hasta'").fetchone()[0])
        self.creditos={}; self.por_cliente=defaultdict(list)
        for i,cl,ad,ag,sg,pr,ini,mb in db.execute('''SELECT l.id,l.cliente_id,c.asesor_id,a.agencia,l.segmento,l.producto_id,l.desembolso,c.mes_bajo
            FROM creditos l JOIN clientes c ON c.id=l.cliente_id JOIN asesores a ON a.id=c.asesor_id ORDER BY l.id'''):
            l=Credito(i,cl,ad,ag,sg,pr,ordinal(ini),mb)
            self.creditos[i]=l;self.por_cliente[cl].append(l)
        for idc,v,reg,desde,n,vence,capital,interes in db.execute('''SELECT c.credito_id,c.version,c.registrado,c.vigente_desde,q.numero,q.vence,q.capital_cent,q.interes_cent
            FROM cronogramas c JOIN cuotas q ON c.id=q.cronograma_id ORDER BY c.credito_id,c.version,q.numero'''):
            versiones=self.creditos[idc].versiones
            if not versiones or versiones[-1][2]!=v: versiones.append((ordinal(reg),ordinal(desde),v,[]))
            versiones[-1][3].append((n,ordinal(vence),capital+interes))
        for cid,n,ef,reg,importe in db.execute('SELECT credito_id,numero,efectiva,registrada,importe_cent FROM abonos ORDER BY efectiva,id'):
            self.creditos[cid].pagos[n].append((ordinal(ef),ordinal(reg),importe))
        for l in self.creditos.values():
            cuotas=l.versiones[-1][3]
            if all(sum(x[2] for x in l.pagos[n])>=total for n,_,total in cuotas):
                l.cerrado=max(max(x[1] for abonos in l.pagos.values() for x in abonos),l.versiones[-1][1],l.versiones[-1][0])
        self.fallos=defaultdict(list)
        for ag,det,res in db.execute('SELECT agencia,detectada,resuelta FROM incidencias_fuente'):
            self.fallos[ag].append((ordinal(det),ordinal(res) if res else self.fin+1))

    def resultados(self):
        """Clave histórica de episodio. Un período continuo de mora de un crédito se cuenta una vez."""
        eventos={}
        for l in self.creditos.values():
            efectiva=version_en(l,self.fin)
            if not efectiva: continue
            hasta=0; episodio=None
            for n,v,total in efectiva[3]:
                if v>=self.fin: break
                _,pago,_,_=cubierto(l.pagos[n],total,self.fin)
                cierre=pago if pago is not None else self.fin+1
                if cierre<=v: continue
                # Un día de cierre al corriente entre atrasos inicia otro episodio.
                if v+1>hasta: episodio=None
                if cierre>=v+31 and v+31<=self.fin:
                    if episodio is None: episodio=f'{l.id}-{n}'
                    eventos[(l.id,n)]=(episodio,v)
                hasta=max(hasta,cierre)
        return eventos

    def corte(self,t):
        if t>self.fin: raise ValueError('El corte excede la fecha observada')
        salida=[]
        for cliente,loans in self.por_cliente.items():
            activos=[]; vencida=False; carga=0
            for l in loans:
                if l.inicio>t or (l.cerrado is not None and l.cerrado<=t): continue
                ver=version_en(l,t)
                if ver is None: continue
                historia=[]; proximas=[]; pendientes=False
                for n,v,importe in ver[3]:
                    abonado,fecha,partes,demora=cubierto(l.pagos.get(n,()),importe,t)
                    if fecha is not None:
                        if v<=t: historia.append((v-fecha,v,fecha,partes,demora))
                        continue
                    pendientes=True
                    if v<=t:  # una cuota que vence hoy sin cubrir tampoco es contacto preventivo
                        vencida=True;break
                    if v<=t+7: carga+=importe-abonado
                    if v<=t+29: proximas.append((n,v,importe,abonado))
                if vencida:break
                if pendientes:activos.append((l,ver[2],historia,proximas))
            if vencida:continue
            for l,version,hist,proximas in activos:
                for n,v,importe,abonado in proximas:
                    baja=int(l.mes_bajo is not None and (date.fromordinal(v).month-l.mes_bajo)%12<2)
                    incidencia=any(a<=t<b for a,b in self.fallos[l.agencia])
                    estado='fuente pendiente' if incidencia else ('historial breve' if len(hist)<4 else 'evaluable')
                    r=dict(corte=t,cliente=cliente,credito=l.id,cuota=n,asesor=l.asesor,segmento=l.segmento,
                        producto=l.producto,vence=v,version=version,importe_cent=importe,pendiente_cent=importe-abonado,
                        carga_cent=carga,estado=estado,estacional=l.mes_bajo is not None,antiguedad_dias=t-l.inicio,
                        temporada_baja=baja,dias_vencer=v-t,creditos_activos=len(activos),cuotas_previas=len(hist),
                        fraccion_cubierta=abonado/importe,carga_7=carga/importe)
                    if len(hist)>=4:
                        reciente=hist[-2:]; previa=hist[-8:-2]; ultimas=hist[-4:]
                        costumbre=median(x[0] for x in previa)
                        margen=median(x[0] for x in reciente)
                        r.update(margen_ultimo=hist[-1][0],margen_reciente=margen,cambio_margen=costumbre-margen,
                            variabilidad=median(abs(x[0]-costumbre) for x in previa),
                            fraccionadas=sum(x[3]>1 for x in ultimas)/4,tardias_previas=sum(x[0]<0 for x in ultimas)/4,
                            demora_registro=max(x[4] for x in ultimas),margen_habitual=costumbre,
                            ultimo_vence=hist[-1][1],ultimo_pago=hist[-1][2],previa_desde=previa[0][1],
                            previa_hasta=previa[-1][1],reciente_desde=reciente[0][1])
                    salida.append(r)
        return salida

def etiqueta(eventos,r):
    evento=eventos.get((r['credito'],r['cuota']))
    if evento:
        ident,vence=evento
        if r['corte']<vence and vence+31<=r['corte']+60: return ident,vence
    return '',0
