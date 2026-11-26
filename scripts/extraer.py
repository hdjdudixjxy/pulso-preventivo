"""Extrae la copia original del ensayo y comprueba su identidad antes de utilizarla."""
from pathlib import Path
import gzip
import hashlib
import shutil

root = Path(__file__).resolve().parents[1]
dest = root/'.salidas/ensayo'
dest.mkdir(parents=True,exist_ok=True)
raw = gzip.decompress((root/'datos/cartera.sqlite.gz').read_bytes())
assert hashlib.sha256(raw).hexdigest() == '3b65c417c2acb70dfc880cafcb954ea2d755bd0d34419da6056ec25eeee633c7'
target = dest/'cartera.sqlite'
if target.exists() and target.read_bytes()!=raw:
    raise SystemExit('Hay una base modificada en el destino. Elige otra carpeta de trabajo.')
target.write_bytes(raw)
shutil.copyfile(root/'datos/modelo.joblib',dest/'modelo.joblib')
print('Ensayo verificado:',dest)

