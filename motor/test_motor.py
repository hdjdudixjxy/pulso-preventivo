import sqlite3
import unittest
from datetime import date,timedelta
from pathlib import Path
import pandas as pd
from cartera import Cartera,etiqueta,ordinal,iso
from modelos import ordenar,seleccionar,medicion,PERIODOS

def base():
    db=sqlite3.connect(':memory:')
    db.executescript(Path(__file__).with_name('esquema.sql').read_text(encoding='utf8'))
    db.execute("INSERT INTO metadata VALUES ('observado_hasta','2026-11-26')")
    db.execute("INSERT INTO asesores VALUES(1,'Trujillo')")
    db.execute("INSERT INTO clientes VALUES(1,1,'La Libertad','comercio',NULL,'2026-01-01')")
    db.execute("INSERT INTO productos VALUES('+Negocios','PEN','mensual',0.145,1.1468)")
    db.execute("INSERT INTO creditos VALUES (1,1,'+Negocios','Micro','2026-01-01',60000,.22,6)")
    db.execute("INSERT INTO cronogramas VALUES(1,1,1,'2026-01-01','2026-01-01','original')")
    for n in range(1,7):
        d=date(2026,n+1,10)
        db.execute('INSERT INTO cuotas VALUES(?,?,?,?,?,?)',(1,n,str(date(2026,n,10)),str(d),10000,500))
        if n<=4:
            db.execute('INSERT INTO abonos VALUES(?,?,?,?,?,?,?)',(n,1,n,str(d-timedelta(days=4)),str(d-timedelta(days=3)),10500,'digital'))
    return db

class Pruebas(unittest.TestCase):
    def setUp(self):self.db=base()
    def tearDown(self):self.db.close()
    def test_corte_inmutable_y_version(self):
        t=ordinal('2026-06-04')
        antes=Cartera(self.db).corte(t)
        self.assertEqual(len(antes),1);self.assertEqual(antes[0]['carga_cent'],10500)
        self.db.execute("INSERT INTO cronogramas VALUES (2,1,2,'2026-06-05','2026-06-07','acuerdo')")
        self.db.execute("INSERT INTO cuotas SELECT 2,numero,inicio_ciclo,CASE WHEN numero=5 THEN '2026-06-18' ELSE vence END,capital_cent,interes_cent FROM cuotas WHERE cronograma_id=1")
        self.db.execute("INSERT INTO abonos VALUES(5,1,5,'2026-06-03','2026-06-06',4000,'agencia')")
        cartera=Cartera(self.db)
        self.assertEqual(antes,cartera.corte(t))
        registrado=cartera.corte(ordinal('2026-06-06'))[0]
        self.assertEqual((registrado['version'],registrado['pendiente_cent']),(1,6500))
        nuevo=cartera.corte(ordinal('2026-06-07'))[0]
        self.assertEqual((nuevo['version'],iso(nuevo['vence'])),(2,'2026-06-18'))
    def test_dia_31_y_ventana(self):
        pago="INSERT INTO abonos VALUES(5,1,5,?,?,10500,'agencia')"
        self.db.execute(pago,('2026-07-10','2026-07-10'))
        self.assertNotIn((1,5),Cartera(self.db).resultados())  # 30 días
        self.db.execute("UPDATE abonos SET efectiva='2026-07-11',registrada='2026-07-12' WHERE id=5")
        eventos=Cartera(self.db).resultados()
        self.assertIn((1,5),eventos)
        row={'credito':1,'cuota':5,'corte':ordinal('2026-05-12')}
        self.assertTrue(etiqueta(eventos,row)[0]);row['corte']-=1
        self.assertFalse(etiqueta(eventos,row)[0])
    def test_abonos_deben_cubrir_total(self):
        self.db.execute("INSERT INTO abonos VALUES(5,1,5,'2026-06-05','2026-06-05',7000,'agencia')")
        self.assertEqual(Cartera(self.db).corte(ordinal('2026-06-09'))[0]['pendiente_cent'],3500)
        self.assertEqual(Cartera(self.db).corte(ordinal('2026-06-11')),[])
        self.db.execute("INSERT INTO abonos VALUES(6,1,5,'2026-06-10','2026-06-12',3500,'agencia')")
        self.assertEqual(Cartera(self.db).corte(ordinal('2026-06-11')),[])
        self.assertEqual(Cartera(self.db).corte(ordinal('2026-06-12'))[0]['margen_ultimo'],0)
    def test_agrupa_atraso_continuo(self):
        e=Cartera(self.db).resultados()
        self.assertEqual(e[1,5][0],e[1,6][0])
    def test_calidad(self):
        self.db.execute("INSERT INTO incidencias_fuente VALUES(1,'Trujillo','2026-06-02','2026-06-05')")
        self.assertEqual(Cartera(self.db).corte(ordinal('2026-06-04'))[0]['estado'],'fuente pendiente')
        self.assertEqual(Cartera(self.db).corte(ordinal('2026-04-04'))[0]['estado'],'historial breve')
    def test_cliente_unico_y_cupo(self):
        df=pd.DataFrame([dict(corte=t,asesor=1,cliente=c,credito=l,cuota=1,vence=t+5,puntaje=score)
                         for t in (100,107) for c,l,score in [(3,6,.9),(3,7,.8),(2,8,.7)]])
        cola=seleccionar(ordenar(df),1)
        self.assertEqual(list(cola.credito),[6,8]);self.assertTrue((cola.groupby(['corte','asesor']).size()<=1).all())
        self.assertFalse(cola.duplicated(['corte','cliente']).any())
    def test_metrica_por_episodio(self):
        calls=pd.DataFrame({'corte':[1,8,8],'vencimiento_real':[10,10,0],'episodio':['a','a','']})
        m=medicion(calls,calls)
        self.assertEqual((m['aciertos'],m['falsas'],m['repeticiones'],m['dias_mediana']),(1,1,1,9))
    def test_periodos_purgados(self):
        a,b,c=[PERIODOS[k] for k in ('entrenamiento','validacion','prueba')]
        self.assertLess(ordinal(a[1])+63,ordinal(b[0]))
        self.assertLess(ordinal(b[1])+63,ordinal(c[0]))
        self.assertLessEqual(ordinal(c[1])+63,ordinal('2026-11-26'))

if __name__=='__main__':unittest.main()
