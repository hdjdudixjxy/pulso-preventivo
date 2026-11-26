# Pulso Preventivo

[**Abrir la aplicación en GitHub Pages**](https://hdjdudixjxy.github.io/pulso-preventivo/) · [Manual y fundamento del concepto (PDF)](docs/manual.pdf)

Bandeja semanal de atención preventiva para créditos MYPE mensuales en soles, con operaciones ficticias de +Negocios y Facilito en La Libertad. Es un prototipo de equipo para el desafío RIE-03 del Cajathon. La persona que usa la demo representa a un asesor y decide el contacto.

## Probar en tres minutos

1. Abre la web. Elige un asesor, la semana y un cupo de 1 a 10 clientes. Compara el orden del modelo con la regla que usa la última cuota.
2. En **Ver expediente**, contrasta las fechas efectivas de pago con los vencimientos. Registra una decisión ficticia con nota y, si corresponde, seguimiento. Recarga y abre **Gestiones**.
3. En **Evaluación del modelo**, abre el cliente 497. Examina sus márgenes y consulta **Ver desenlace a 60 días**. Repite con la falsa alarma estacional del cliente 182 y el episodio omitido del 24.
4. **Espacio de demo** permite trasladar las gestiones a otro navegador. El código es una credencial de demostración. Cada espacio genera sus propios registros sobre la misma cartera. Usa únicamente notas ficticias.

## Arquitectura desplegada

- **GitHub Pages** sirve HTML, CSS, JavaScript, la identidad visual del equipo y el manual desde `docs/`.
- **Servicio HTTP y D1**. El Worker en `api/worker.mjs` consulta una base SQLite gestionada en la nube y persiste cada gestión. El navegador conserva el identificador aleatorio del espacio. El servidor almacena su huella y valida el asesor, obligación y corte de cada registro. La selección de asesor simula un rol en la demo. Una implantación institucional requeriría autenticación y autorización individual.
- **Motor Python**. El modelo de árboles potenciados ya entrenado genera los candidatos antes del despliegue. La base contiene 39 cortes semanales del 2 de marzo al 23 de noviembre de 2026. La API ordena los candidatos, elige una obligación por cliente, aplica la pausa de 28 días tras la gestión y el cupo. Si se gestionó un caso, se conserva visible en su misma semana. Las anotaciones de la demo se guardan con la fecha del corte.
- **Trazabilidad**. El historial usa el cronograma vigente y los pagos conocidos al corte. El desenlace tiene una consulta aparte y solo se muestra con 60 días completos de observación. El puntaje ordena las alertas. Ninguna facilidad crediticia se ejecuta desde la aplicación.
- **Fuente**. Copia de `pulso_motor/ensayo/cartera.sqlite`. SHA-256 del archivo descomprimido: `3b65c417c2acb70dfc880cafcb954ea2d755bd0d34419da6056ec25eeee633c7`. Las diez tablas originales conservan sus registros. La columna adicional en gestiones separa espacios. Las demás tablas nuevas almacenan semanas, candidatos, incidencias de calidad por corte y el control de la importación. La web no tiene conexión con clientes reales ni con el core bancario.

## Reproducir en local

Se necesita Python 3.12 y Node.js 24. El motor usa las versiones de `motor/requirements.txt`. Desde la raíz del repositorio:

```shell
python -m venv .venv
```

Activa el entorno con `.venv\Scripts\activate` en Windows o `source .venv/bin/activate` en Linux/macOS.

```shell
python -m pip install -r motor/requirements.txt
python scripts/extraer.py
python scripts/preparar.py --ensayo .salidas/ensayo --destino .salidas
node scripts/compilar.mjs
node scripts/local.mjs .salidas/web.sqlite
```

Abre http://127.0.0.1:4173. Para una reproducción independiente usa `python motor/pulso.py demo --dir otra-carpeta` con la semilla predeterminada 731. El importador del modelo carga el artefacto propio distribuido en este repositorio.

## Publicación y datos

Pages publica la carpeta `/docs` de la rama `main`. El Worker requiere el binding D1 `DB`, las migraciones de `drizzle/` y el módulo compilado `dist/server/index.js`. La identidad de la instancia desplegada está en `.openai/hosting.json`. Para una nueva instancia ajusta el origen de Pages permitido, la URL del servicio en el cliente y la identidad de despliegue.

La preparación genera el manifiesto de lotes y las cargas comprimidas en `.salidas/lotes`. Publica el Worker con el manifiesto correspondiente antes de importar en una base vacía. Ejecuta `python scripts/importar.py --url URL_DEL_SERVICIO --lotes .salidas/lotes`. Cada lote se verifica por SHA-256 y se inserta junto con su marca en una sola transacción. Los reintentos conservan una única copia. Esta importación inicial se destina al ensayo distribuido. Una cartera diferente necesita una nueva base o una migración versionada específica.

## Evidencia

La prueba temporal reservó 30 semanas (marzo a septiembre de 2026), con 1.150 contactos por método: 186 episodios únicos anticipados por el modelo, frente a 156 con la regla. La mediana de anticipación fue de 14 y 16 días, respectivamente. El modelo dejó 962 falsas alertas y 2 repeticiones. El estudio simula detección y no mide el efecto de llamar al cliente. [Resultados completos](motor/resultados.json) · [SBS, créditos directos por tipo y situación, septiembre de 2026](https://intranet2.sbs.gob.pe/estadistica/financiera/2026/Setiembre/C-1228-se2026.XLS)

