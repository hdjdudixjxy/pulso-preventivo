"""Carga lotes verificables, reintentables y ordenados por dependencias al servicio publicado."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import groupby
import json
from pathlib import Path
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--lotes', type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((ROOT/'api/manifest.json').read_text(encoding='utf8'))

def upload(pair):
    i, meta = pair
    data=(args.lotes/meta['file']).read_bytes()
    for attempt in range(5):
        try:
            req=urllib.request.Request(args.url.rstrip('/')+'/api/importar/'+str(i),data=data,
                  headers={'Content-Type':'application/octet-stream','User-Agent':'PulsoImporter/1'})
            with urllib.request.urlopen(req,timeout=90) as resp:
                result=json.load(resp)
            if result['filas']!=meta['n']:
                raise ValueError('Cantidad de filas distinta en lote '+str(i))
            return result['filas']
        except (OSError,ValueError) as err:
            if attempt==4 or isinstance(err,urllib.error.HTTPError) and err.code in (400,403,404):
                if isinstance(err,urllib.error.HTTPError):
                    raise RuntimeError(f'Lote {i}, HTTP {err.code}: '+err.read(350).decode('utf8','replace')) from err
                raise
            time.sleep(2**attempt)
for table, pairs in groupby(enumerate(manifest), lambda p:p[1]['table']):
    with ThreadPoolExecutor(max_workers=4) as pool:
        print(table,sum(pool.map(upload,list(pairs))),flush=True)

