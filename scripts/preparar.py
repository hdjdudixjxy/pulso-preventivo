"""Reconstruye los cortes y prepara una importación verificable a D1, sin datos personales."""
import argparse
from datetime import timedelta, date
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "motor"))
from cartera import Cartera, ordinal, iso, etiqueta
from modelos import puntuar, explicar
import joblib
import pandas as pd

TABLES = ["metadata", "asesores", "clientes", "productos", "creditos", "cronogramas",
          "cuotas", "abonos", "incidencias_fuente", "gestiones", "semanas", "candidatos", "revision"]
START = date(2026, 3, 2)
LAST = date(2026, 11, 23)

def build(db, model):
    cartera = Cartera(db)
    eventos = cartera.resultados()
    day = START
    while day <= LAST:
        cut = day.isoformat()
        rows = cartera.corte(ordinal(cut))
        df = pd.DataFrame(rows)
        ok = df[df.estado == 'evaluable'].copy()
        ok['puntaje'] = puntuar(model['estimador'], ok)
        ok = explicar(model, ok)
        db.execute("INSERT INTO semanas VALUES (?)", (cut,))
        for r in ok.to_dict('records'):
            ep, due = etiqueta(eventos, r)
            db.execute("INSERT INTO candidatos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                cut, r['asesor'], r['cliente'], r['credito'], r['cuota'], r['version'], r['producto'], r['segmento'],
                iso(r['vence']), int(r['pendiente_cent']), int(r['carga_cent']), r['puntaje'], r['margen_ultimo'],
                r['margen_habitual'], r['margen_reciente'], r['evidencia'], r['pregunta_sugerida'],
                int(r['temporada_baja']), int(r['cuotas_previas']), iso(due+31) if ep else None, int(r['estacional'])))
        db.executemany("INSERT INTO revision VALUES (?,?,?,?,?,?)", (
            (cut,r['asesor'],r['cliente'],r['credito'],r['cuota'],r['estado']) for r in rows if r['estado']!='evaluable'))
        day += timedelta(days=7)
    db.commit()

def export(db, folder):
    folder.mkdir(exist_ok=True, parents=True)
    manifest = []
    for table in TABLES:
        cols = [r[1] for r in db.execute(f'PRAGMA table_info({table})')]
        cursor = db.execute(f'SELECT * FROM {table} ORDER BY rowid')
        while rows := cursor.fetchmany(1200):
            raw = json.dumps(rows, ensure_ascii=False, separators=(',',':'), allow_nan=False).encode()
            packet = gzip.compress(raw, mtime=0)
            name = f'{len(manifest):04d}.gz'
            (folder/name).write_bytes(packet)
            manifest.append(dict(table=table, cols=cols, n=len(rows), file=name,
                                 hash=hashlib.sha256(packet).hexdigest()))
    (ROOT/'api/manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',',':')), encoding='utf8')
    print('Lotes', len(manifest), 'Filas', sum(x['n'] for x in manifest), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ensayo', type=Path, required=True)
    parser.add_argument('--destino', type=Path, required=True)
    args = parser.parse_args()
    args.destino.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(args.destino/'web.sqlite')
    with sqlite3.connect(args.ensayo/'cartera.sqlite') as origen:
        if origen.execute('SELECT COUNT(*) FROM gestiones').fetchone()[0]:
            raise ValueError('Use el ensayo sintético inicial sin notas de usuarios.')
        origen.backup(db)
    db.executescript((ROOT/'api/ampliacion.sql').read_text(encoding='utf8'))
    build(db, joblib.load(args.ensayo/'modelo.joblib'))
    export(db, args.destino/'lotes')
    db.close()

