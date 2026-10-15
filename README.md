# bestas-crm

[![tests](https://github.com/aragonbaltazarut-lang/bestas-crm/actions/workflows/tests.yml/badge.svg)](https://github.com/aragonbaltazarut-lang/bestas-crm/actions/workflows/tests.yml)

El CRM de [BESTAS](https://bestasba.com), productora de eventos y sello de música house de Buenos Aires.

Los contactos de la productora estaban repartidos en planillas que no se hablaban entre sí. Por un lado, el export de entradas de la ticketera de cada fecha. Por otro, listas armadas a mano de nombres y mails —de RRPP, de clientes, de otras productoras con las que trabajamos—, cada una con su propio desorden. Este proyecto las une en una sola base SQLite. Ahí una persona es una sola aunque aparezca en tres planillas. Con eso se puede preguntar quién compra, para quién compra, quién vuelve, quién vendió cada entrada y quién está en más de una base.

Empezó en octubre de 2026 como la migración de esas planillas a código. Lo desarrollo con asistencia de IA (Claude Code), igual que el sitio de la marca.

Los datos de `datos/ejemplo/` son inventados. Las bases reales tienen nombres, mails y DNI de personas: no se suben al repositorio (ver `.gitignore`).

## Qué hace

### Importar

- **El export de entradas de Bombo.** Cada entrada tiene un comprador, un asistente —a quien se le pasó la entrada— y un vendedor: la productora o el RRPP que la vendió. El CRM guarda los tres. Así se ve quién compra para otros, que en los combos de 4 es la mitad de las entradas, y cuánto vendió cada RRPP.
- **Listas armadas a mano, sin pedir que las ordenen antes.** Lee todas las hojas del archivo, busca los mails en toda la hoja y toma como nombre la celda de la izquierda. Si la columna tiene un título arriba (por ejemplo "MUJERES"), lo anota y, si dice el género, lo usa. Si hay una columna "DNI", la toma.
- **Se puede correr dos veces.** Reimportar la misma planilla no duplica personas, entradas ni incidencias.
- **Registra lo que no puede cargar en vez de frenar.** Un mail sin dominio, un nombre sin mail o un asistente sin mail quedan como incidencias, con la hoja y la celda donde están, para revisarlas a mano. Los encabezados y las notas que alguien dejó en la columna del mail ("no comisiona", "-") no se confunden con personas.

### Limpiar

- **Separa lo que viene pegado al nombre.** En las listas de RRPP el nombre trae quién lo trajo o el rol: `Ana Pérez (BOMBO) 👑` queda como `Ana Pérez`, con `BOMBO` en las notas, y `Juan Gómez RRPP CROBAR` queda como `Juan Gómez`, con `RRPP CROBAR`. Cuando una celda tiene dos mails (`a@x.com // b@x.com`), guarda el primero y anota el otro.
- **Corrige mails con el dominio mal escrito.** `gmail.con`, `gamail.com` o `hotmai.l.com` pasan a `gmail.com` y `hotmail.com`, y cada corrección queda como incidencia para confirmarla. Solo corrige contra los dominios más comunes y cuando el parecido es muy alto: `hotmail.com.ar` o `ymail.com` existen y no se tocan, y tampoco el mismo proveedor con el dominio de otro país (`yahoo.com.br`); `gmail.com.ar` no existe y se corrige.
- **Limpia lo que viene sucio**: mails en mayúsculas o con espacios, nombres en minúscula o con dos puntos al final, DNI que Excel guardó como `40123456.0`, el género que Bombo anota a veces en inglés y a veces en castellano.

### Una persona, una ficha

- **Unifica personas.** Las identifica por mail y, si no hay mail, por DNI. En Gmail, `juan.perez+bestas@gmail.com` y `juanperez@gmail.com` son la misma casilla, y el CRM los toma como la misma persona. Un dato que ya estaba no se pisa con otro distinto: solo se completan los vacíos. La excepción es un nombre con caracteres rotos (`Pe�a`), que se reemplaza cuando llega la versión sana desde otra planilla.
- **No une por nombre: lo propone.** Dos "Juan Pérez" pueden ser dos personas, y mezclar sus datos es peor que un duplicado. El reporte "Posibles duplicados" muestra el mismo nombre con otro mail, y si son la misma persona se unen a mano con `python -m crm unir`. Las entradas y los orígenes pasan a la ficha que queda, sus datos completan los vacíos y el otro mail queda como alias: reimportar una planilla no vuelve a crear la ficha borrada. Cada unión queda registrada.
- **Estima el género por el nombre de pila** cuando ninguna planilla lo dice. Usa un diccionario propio de nombres argentinos (`crm/nombres.csv`), con los apodos de acá (Agus, Fede, Cami), y no estima los que son de los dos: Juli puede ser Julieta o Julián, y "Jose" sin tilde acá suele ser Josefina, mientras que "José" es hombre. Corre en la misma máquina: los nombres no se mandan a ningún servicio de afuera. Cada persona guarda de dónde salió su género —`declarado` en la ticketera, `lista` por el título de la columna, o `nombre`— y uno más confiable reemplaza a uno menos confiable, nunca al revés. Lo que dice el nombre se guarda aparte aunque haya otro dato, y si chocan, la persona aparece en el reporte "Género a revisar".
- **Distingue personas de organizaciones**: productoras, medios, cuentas como "Fiestas Electrónicas" o casillas genéricas (`info@`, `prensa@`). Las organizaciones no llevan género.
- **El historial de cada uno en las fechas**: a cuántas fue, la primera y la última, cuántas entradas compró y cuánto gastó. Es una vista de SQL (`historial`): se calcula al consultarla y nunca queda desactualizada.

### Usar los datos

- **Reportes en SQL**: personas por fuente, personas que están en más de una base, el público que volvió, mejores compradores, ventas por tanda y por vendedor, género y de dónde salió, género a revisar, organizaciones, posibles duplicados, bajas e incidencias abiertas.
- **Exporta segmentos a CSV** para un mail o un público de Meta: por fuente, por género, compradores o no compradores, o quienes fueron a varias fechas.
- **Lista de bajas.** Quien pide no recibir más mails no vuelve a salir en ninguna exportación (Ley 25.326, art. 27). La baja es de la casilla, como en los servicios de mailing: sigue valiendo si esa casilla vuelve a llegar en otra planilla, y alcanza con que uno de los mails de la persona esté dado de baja.
- **API con FastAPI**: buscar personas con filtros y de a páginas, ver la ficha de cada una con su historial, sus orígenes y sus entradas, unir duplicados, registrar bajas y marcar incidencias como resueltas. Con la variable `CRM_TOKEN` pide un token en cada pedido.
- **Migraciones.** El esquema es una lista de migraciones numeradas, y la base sabe hasta cuál tiene aplicada (`PRAGMA user_version`). Una tabla nueva no obliga a borrar la base y reimportar, que sería perder lo que se cargó a mano: las bajas, las uniones y las incidencias resueltas.

## Qué tan bien estima el género

Con las bases reales de la productora (2.636 personas), el género quedó así:

| De dónde sale | Personas |
|---|---|
| Declarado en la ticketera | 11 |
| Título de la columna de la lista (mujeres u hombres) | 297 |
| Estimado por el nombre | 2.177 |
| Sin dato (nombre ambiguo o desconocido) | 137 |

Para medir la estimación, se comparó contra las 308 personas que ya tenían el género por otra vía: coincide en 274, no estima en 30 (apodos ambiguos como Manu o Juli) y choca en 4. Los 4 choques son nombres de hombre en una columna de mujeres: el error está en la planilla, no en el nombre.

## Cómo correrlo

Necesita Python 3.11 o más nuevo.

```bash
python -m venv .venv
.venv\Scripts\activate          # en Linux o macOS: source .venv/bin/activate
pip install -r requirements.txt

python -m crm bombo datos/ejemplo/bombo-ejemplo.xlsx --evento "Evento Ejemplo" --fecha 2026-05-16
python -m crm bombo datos/ejemplo/bombo-ejemplo-2.xlsx --evento "Evento Ejemplo 2" --fecha 2026-08-22
python -m crm lista datos/ejemplo/lista-ejemplo.xlsx --fuente "Lista Ejemplo"
python -m crm lista datos/ejemplo/clientes-ejemplo.xlsx --fuente "Clientes Ejemplo"
python -m crm reporte
```

```
6 entradas, 5 personas nuevas, 1 incidencias
3 entradas, 1 personas nuevas, 0 incidencias
6 contactos, 2 personas nuevas, 1 repetidos, 2 incidencias
5 contactos, 3 personas nuevas, 0 repetidos, 3 incidencias

Público que volvió

nombre        email                     fechas  primera     ultima      gastado
------------  ------------------------  ------  ----------  ----------  -------
Ana Ejemplo   ana.ejemplo@example.com   2       2026-05-16  2026-08-22  73700.0
Bruno Prueba  bruno.prueba@example.com  2       2026-05-16  2026-08-22  30900.0

Ventas por vendedor

evento            vendedor            entradas  compradores  recaudado
----------------  ------------------  --------  -----------  ---------
Evento Ejemplo    Bestas Productions  4         3            120600.0
Evento Ejemplo    Rocío Vendedora     2         1            47800.0
Evento Ejemplo 2  Rocío Vendedora     2         2            58800.0
Evento Ejemplo 2  Bestas Productions  1         1            30900.0

Incidencias abiertas

fuente                  ubicacion    tipo                detalle
----------------------  -----------  ------------------  -------------------------------------
Bombo · Evento Ejemplo  fila 6       asistente sin mail  Elena Muestra
Clientes Ejemplo        RRPP!A3      nombre sin mail     Medio Ejemplo (al lado: no comisiona)
Clientes Ejemplo        CLIENTES!A3  nombre sin mail     IGNACIO SIN MAIL
Clientes Ejemplo        CLIENTES!A5  nombre sin mail     Venta en puerta (al lado: -)
Lista Ejemplo           F7           mail inválido       martina.muestra@example
Lista Ejemplo           N9           nombre sin mail     Nombre Sin Mail
```

Para sacar un segmento (las bajas nunca salen):

```bash
python -m crm exportar mujeres.csv --genero mujer
python -m crm exportar no-compraron.csv --fuente "Lista Ejemplo" --no-compraron
python -m crm exportar volvieron.csv --fechas 2
```

Bajas y duplicados:

```bash
python -m crm baja lucia.demo@example.com --motivo "lo pidió por mail"
python -m crm unir 12 34        # la ficha 34 se une a la 12 y se borra
```

Si se suman nombres a `crm/nombres.csv`, no hace falta reimportar:

```bash
python -m crm enriquecer
```

La API:

```bash
uvicorn crm.api:app --reload
```

Y en http://127.0.0.1:8000/docs se puede probar cada ruta:

| Ruta | Qué hace |
|---|---|
| `GET /personas?buscar=&fuente=&genero=&tipo=&limite=&desde=` | Busca por nombre o mail, filtra por fuente, género o tipo, y devuelve de a páginas con el total |
| `GET /personas/{id}` | La ficha: datos, otros mails, orígenes, historial en las fechas, entradas y si recibe mails |
| `POST /personas/{id}/unir` | Une a esta persona la ficha `{"se_va": id}`, que se borra |
| `GET /bajas` · `POST /bajas` | La lista de bajas, y registrar una: `{"email": "...", "motivo": "..."}` |
| `GET /incidencias` | Lo que quedó para revisar a mano |
| `POST /incidencias/{id}/resolver` | Marca una incidencia como revisada |
| `GET /reportes` | Los reportes en JSON |

Sin `CRM_TOKEN` la API queda abierta, que está bien para usarla en la propia compu. En un servidor, con `CRM_TOKEN=<algo largo y al azar>` cada pedido tiene que traer `Authorization: Bearer <ese valor>`.

Los tests:

```bash
pytest
```

Las planillas de ejemplo se regeneran con `python scripts/generar_ejemplos.py`. Los tests arman las suyas en una carpeta temporal.

## Cómo está armado

```
crm/
  db.py          el esquema, como migraciones numeradas
  normalizar.py  limpieza de mails (y dominios mal escritos), nombres, notas, DNI y teléfonos
  enriquecer.py  género por el nombre y personas u organizaciones
  nombres.csv    el diccionario de nombres de pila
  personas.py    alta, unificación y unión de personas, orígenes e incidencias
  importar.py    un importador por formato: Bombo y listas sueltas
  bajas.py       la lista de bajas
  reportes.py    los reportes, en SQL
  exportar.py    segmentos a CSV
  api.py         la API
  __main__.py    la línea de comandos
```

Las tablas:

- `personas`: una por persona, con su mail y la clave con la que se compara (`email_clave`), el tipo (persona u organización), el género con su origen, el género que dice el nombre y las notas que venían pegadas al nombre.
- `alias`: los otros mails de una persona, que llegan al unir dos fichas.
- `eventos` y `entradas`: cada entrada con su comprador, su asistente y su vendedor.
- `origenes`: de qué planilla salió cada persona y en qué papel ("compró", "asistió", "columna mujeres"). Una persona puede tener varios.
- `bajas`: los mails que pidieron no recibir más.
- `uniones`: cada unión hecha a mano, con la ficha que se fue.
- `incidencias`: lo que no se pudo cargar, con la celda donde está.
- `historial` (vista): fechas, primera y última, entradas compradas y gastado de cada persona.

## Hacia dónde va

Hoy el CRM cubre al público. Una productora con sello tiene más contactos que eso —RRPP, artistas, la gente del sello, marcas y venues—, y cada uno pasa por sus propias etapas.

### Público

- [ ] **Etapas de contacto**: nuevo, primera compra, volvió, habitual, inactivo. Se calculan solas a partir de `historial`.
- [ ] **Grupos de amigos**: con quién compra para quién, encontrar al que trae al grupo. Le escribís a uno y vienen cuatro.
- [ ] **Afinidad por artista**: avisarle a quien ya vio a un DJ cuando vuelve.
- [ ] **Preventa para los habituales**, con un link propio para medir cuántos compran.
- [ ] **Curva de ventas** por fecha y por tanda, para decidir cuándo abrir la siguiente (hace falta la fecha de compra).
- [ ] **Encuesta después de cada fecha**, guardada en la ficha de cada persona.

### RRPP

- [ ] **Lista de invitados digital con control en la puerta**: reemplaza las planillas de RRPP y deja registrado quién entró de verdad.
- [ ] **Liquidación de comisiones** por fecha y por tanda.
- [ ] **Calidad del público de cada RRPP**: cuánta gente nueva trae y cuánta vuelve.

### Artistas

- [ ] **Ficha de cada DJ**, residente o invitado: contacto o agencia, fee, rider, fechas en las que tocó y cuánta gente movió.
- [ ] **Etapas de booking**: contactado, oferta, confirmado, pagado.

### Sello

- [ ] **Lista de promo** de cada lanzamiento: a quién se mandó, quién respondió y quién lo pasó.
- [ ] **Demos recibidos**, con etapas: recibido, escuchado, preseleccionado, firmado.
- [ ] **Regalías y repartos** por lanzamiento y por artista.

### Marcas y venues

- [ ] **Ficha de cada marca y cada venue**: fechas, contacto, condiciones, cuándo renovar.
- [ ] **Reporte para sponsors** con datos del público sin identificar a nadie.

### Agentes automáticos

- [ ] **Carga automática** de las ventas de cada fecha apenas cierra.
- [ ] **Reporte del día siguiente** al equipo: ventas, gente nueva, quién volvió, ranking de RRPP.
- [ ] **Seguimiento por etapa**: arma el mail cuando alguien cambia de etapa y lo deja para que una persona lo apruebe.
- [ ] **Promo del sello**: cuando sale un disco, propone a qué DJs mandárselo.
- [ ] **Preguntas en lenguaje natural** sobre la base, solo de lectura.

Los agentes trabajan sobre datos personales: anonimizados o con un modelo que corra local, con el mismo criterio con el que el género no se estima con un servicio de afuera.

### Fuentes y conexiones

- [ ] **Importadores para las otras ticketeras** (Flashpass, PlanOut, Tickit). Con el esquema como está, cada una es un importador nuevo.
- [ ] **Bajas desde el propio mail**, con un link firmado para cada destinatario.
- [ ] **Conexión con el sitio**: que el formulario de contacto y la suscripción al newsletter entren al CRM, y que los dos compartan la lista de eventos.

## Licencia

MIT. Ver `LICENSE`.
