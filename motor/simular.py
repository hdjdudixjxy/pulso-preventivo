"""Cartera ficticia. Las trayectorias latentes nunca se guardan en la base operativa."""
import calendar
import math
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

FIN = date(2026, 11, 26)
ORIGEN = date(2022, 1, 1)
def mes(d, pasos):
    total = d.year * 12 + d.month - 1 + pasos
    y, m = divmod(total, 12)
    return date(y, m+1, min(d.day, calendar.monthrange(y,m+1)[1]))

def dia(d, n):
    return d + timedelta(days=n)

def cuotas(principal, tea, plazo):
    tasa = (1+tea)**(1/12)-1
    cuota = round(principal*tasa/(1-(1+tasa)**-plazo))
    saldo = principal
    for i in range(1, plazo+1):
        interes = round(saldo*tasa)
        capital = saldo if i==plazo else cuota-interes
        yield capital,interes
        saldo -= capital

def crear(db, n=1200, semilla=731):
    rng=random.Random(semilla)
    db.executescript(Path(__file__).with_name('esquema.sql').read_text(encoding='utf8'))
    db.executemany('INSERT INTO metadata VALUES (?,?)',[('fuente','SINTETICA'),('observado_hasta',str(FIN)),('semilla',str(semilla))])
    agencias=['Trujillo','La Esperanza','El Porvenir','Moche']
    db.executemany('INSERT INTO asesores VALUES (?,?)',enumerate(agencias,1))
    db.executemany('INSERT INTO productos VALUES (?,?,?,?,?)',[
        ('+Negocios','PEN','mensual',.145,1.1468),('Facilito','PEN','mensual',.309,1.1468)])
    cid=vid=0
    for cliente in range(1,n+1):
        micro=rng.random()<.44
        agente=rng.randrange(1,5)
        alta=dia(ORIGEN, rng.randrange(0, (FIN-ORIGEN).days-7) if rng.random()<.40 else rng.randrange(0,390))
        sector=rng.choice(['comercio','servicios','agrocomercio','transporte','manufactura'])
        baja=rng.choice([2,4,8,10]) if rng.random()<.28 else None
        db.execute('INSERT INTO clientes VALUES (?,?,?,?,?,?)',(cliente,agente,'La Libertad',sector,baja,str(alta)))
        # Episodios progresivos, choques abruptos y recuperación. Algunos cambios se resuelven sin mora.
        trayectoria=[]
        base=rng.uniform(.55,1.45)
        tension=0.; restantes=0; pendiente=0.
        for _ in range(66):
            if restantes==0 and rng.random()<(.085 if micro else .064):
                restantes=rng.randint(3,9); pendiente=rng.uniform(.23,.69)
            if restantes:
                tension=min(4.0,tension+pendiente); restantes-=1
            else:
                tension=max(0.,tension*.56-.10)
            trayectoria.append(max(0,tension+rng.gauss(0,.18)))
        habitual=rng.uniform(.5,9.0)

        def credito(desembolso, secundario):
            nonlocal cid,vid
            cid+=1
            producto='Facilito' if (micro and rng.random()<.65) or (secundario and rng.random()<.55) else '+Negocios'
            bajo,alto=(500,10000) if producto=='Facilito' else ((3000,20000) if micro else (10000,75000))
            principal=rng.randrange(bajo,alto+1)*100
            plazo=rng.choice([9,12,15,18]) if producto=='Facilito' else rng.choice([12,18,24])
            tea=round(rng.uniform(.31,.74) if producto=='Facilito' else rng.uniform(.18,.55),4)
            db.execute('INSERT INTO creditos VALUES (?,?,?,?,?,?,?,?)',(cid,cliente,producto,'Micro' if micro else 'Pequeña',str(desembolso),principal,tea,plazo))
            fechas=[mes(desembolso,j) for j in range(1,plazo+1)]
            importes=list(cuotas(principal,tea,plazo))
            def version(v,reg,desde,motivo):
                nonlocal vid
                vid+=1
                db.execute('INSERT INTO cronogramas VALUES (?,?,?,?,?,?)',(vid,cid,v,str(reg),str(desde),motivo))
                db.executemany('INSERT INTO cuotas VALUES (?,?,?,?,?,?)',[
                    (vid,i,str(desembolso if i==1 else fechas[i-2]),str(f),cap,inter)
                    for i,(f,(cap,inter)) in enumerate(zip(fechas,importes),1)])
            version(1,desembolso,desembolso,'original')
            if rng.random()<.19:
                cambio=rng.randrange(3,plazo-1)
                reg=dia(fechas[cambio],-18)
                if reg<=FIN:
                    desplaza=rng.randrange(4,12)
                    fechas[cambio:]=[dia(f,desplaza) for f in fechas[cambio:]]
                    version(2,reg,dia(reg,2),'cambio pactado de fecha')
            for i,(vence,(cap,inter)) in enumerate(zip(fechas,importes),1):
                idx=(vence.year-ORIGEN.year)*12+vence.month-1
                if idx>=len(trayectoria) or vence>dia(FIN,18):
                    break
                estacional=baja is not None and (vence.month-baja)%12 in (0,1)
                nivel=trayectoria[idx]
                margen=habitual-2.3*nivel-(3.3 if estacional else 0)+rng.gauss(0,2.0)
                demora=max(-14,round(-margen))
                # Un impago se realiza como fecha y monto de abonos, nunca como etiqueta precalculada.
                p=1/(1+math.exp(4.6-1.48*nivel-math.log(base)))
                if rng.random()<p:
                    demora=rng.randint(31,75)
                elif rng.random()<.055+.04*nivel:
                    demora=rng.randint(1,19)
                total=cap+inter
                final=dia(vence,demora)
                partes=[(final,total)]
                if rng.random()<.16+.075*nivel:
                    parcial=round(total*rng.uniform(.26,.70))
                    partes=[(min(dia(final,-2),dia(vence,-1)),parcial),(final,total-parcial)]
                for ef,importe in partes:
                    registro=dia(ef,rng.choices([0,1,2,3],weights=[83,12,4,1])[0])
                    if registro<=FIN:
                        db.execute('INSERT INTO abonos(credito_id,numero,efectiva,registrada,importe_cent,canal) VALUES (?,?,?,?,?,?)',
                                   (cid,i,str(ef),str(registro),importe,rng.choice(['agencia','agente','digital'])))
            return fechas[-1]

        inicio=alta
        while inicio<=FIN:
            ultimo=credito(inicio,False)
            if rng.random()<.24:
                adicional=dia(inicio,rng.randint(40,180))
                if adicional<=FIN: credito(adicional,True)
            inicio=dia(ultimo,rng.randint(5,48))
    for ag in agencias:
        for _ in range(26):
            d=dia(ORIGEN,rng.randrange((FIN-ORIGEN).days))
            fin=dia(d,rng.randint(1,3))
            db.execute('INSERT INTO incidencias_fuente(agencia,detectada,resuelta) VALUES (?,?,?)',(ag,str(d),str(fin) if fin<=FIN else None))
    db.execute('ANALYZE')
    db.commit()
