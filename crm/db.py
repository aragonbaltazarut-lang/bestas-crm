"""La base SQLite y sus migraciones.

El esquema no se escribe de una vez: es una lista de migraciones numeradas, y la
base guarda en `PRAGMA user_version` hasta cuál se aplicó. Al conectar se corren
las que faltan, cada una en su transacción. Así una tabla nueva no obliga a borrar
la base y reimportar, que es perder lo que se cargó a mano (bajas, uniones,
incidencias resueltas). Una migración que ya se aplicó no se edita nunca: se suma otra.
"""

import sqlite3
from datetime import datetime, timezone

# 1 · Personas, eventos, entradas, de dónde salió cada contacto e incidencias.
V1 = """
CREATE TABLE IF NOT EXISTS personas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT,             -- normalizado: minúsculas, sin espacios, dominio corregido
    email_clave TEXT UNIQUE,      -- con la que se compara: en Gmail, sin puntos ni '+algo'
    nombre      TEXT NOT NULL,
    tipo        TEXT NOT NULL DEFAULT 'persona',  -- 'persona' | 'organizacion'
    dni         TEXT,
    telefono    TEXT,
    genero      TEXT,             -- 'mujer' | 'hombre' | NULL si no se sabe
    genero_origen TEXT,           -- 'declarado' (ticketera) | 'lista' (título de columna) | 'nombre' (estimado)
    genero_por_nombre TEXT,       -- lo que dice el nombre, siempre: si choca con genero, se revisa
    notas       TEXT,             -- lo que venía pegado al nombre: '(BOMBO)', otro mail
    creada      TEXT NOT NULL,
    actualizada TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eventos (
    slug    TEXT PRIMARY KEY,
    nombre  TEXT NOT NULL,
    fecha   TEXT                  -- AAAA-MM-DD
);

CREATE TABLE IF NOT EXISTS entradas (
    id           TEXT PRIMARY KEY,  -- el id de la ticketera
    evento_slug  TEXT NOT NULL REFERENCES eventos(slug),
    comprador_id INTEGER NOT NULL REFERENCES personas(id),
    asistente_id INTEGER REFERENCES personas(id),  -- NULL si la entrada se pasó a alguien sin mail
    tanda        TEXT NOT NULL,     -- 'Early Bird', 'Tier 1 Combo 4 Pax'...
    precio       REAL NOT NULL,
    estado       TEXT NOT NULL
);

-- Una persona puede venir de varias planillas: acá queda cada una.
CREATE TABLE IF NOT EXISTS origenes (
    persona_id  INTEGER NOT NULL REFERENCES personas(id),
    fuente      TEXT NOT NULL,      -- 'Bombo · The Bow', 'Base de contactos'
    detalle     TEXT NOT NULL,      -- 'compró', 'asistió', 'columna mujeres'
    PRIMARY KEY (persona_id, fuente, detalle)
);

-- Lo que no se pudo cargar o hay que revisar a mano. Nunca frena la importación.
CREATE TABLE IF NOT EXISTS incidencias (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente    TEXT NOT NULL,
    ubicacion TEXT NOT NULL,        -- celda o fila de la planilla
    tipo      TEXT NOT NULL,
    detalle   TEXT NOT NULL,
    creada    TEXT NOT NULL,
    resuelta  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (fuente, ubicacion, tipo)
);

CREATE INDEX IF NOT EXISTS personas_dni ON personas (dni);
CREATE INDEX IF NOT EXISTS origenes_fuente ON origenes (fuente);
CREATE INDEX IF NOT EXISTS entradas_comprador ON entradas (comprador_id);
CREATE INDEX IF NOT EXISTS entradas_asistente ON entradas (asistente_id);
"""

# 2 · Lo que tienen las bases de las ticketeras y los CRM de eventos: quién vendió
# cada entrada, la lista de bajas, los mails de más de una persona, el registro de
# las uniones y el historial de cada uno en las fechas.
V2 = """
-- Quién vendió la entrada: en Bombo, el 'Team Lead' (la productora o un RRPP).
ALTER TABLE entradas ADD COLUMN vendedor TEXT;

-- Quien pidió no recibir más mails (Ley 25.326, art. 27). Va por la clave del mail,
-- no por persona: la baja es de la casilla, y sigue valiendo aunque esa casilla
-- vuelva a llegar en otra planilla o la persona se una con otra.
CREATE TABLE bajas (
    email_clave TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    motivo      TEXT,
    creada      TEXT NOT NULL
);

-- Otros mails de una persona: el de cada ficha que se unió a ella. Al reimportar,
-- un mail de acá se reconoce como de la persona que quedó.
CREATE TABLE alias (
    email_clave TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    persona_id  INTEGER NOT NULL REFERENCES personas(id)
);
CREATE INDEX alias_persona ON alias (persona_id);

-- Cada unión hecha a mano. La ficha que se fue ya no existe: se guarda su nombre y su mail.
CREATE TABLE uniones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    queda_id     INTEGER NOT NULL REFERENCES personas(id),
    se_va_id     INTEGER NOT NULL,
    se_va_nombre TEXT NOT NULL,
    se_va_email  TEXT,
    creada       TEXT NOT NULL
);

-- Lo de cada persona en las fechas: a cuántas fue (tenía una entrada a su nombre),
-- la primera y la última, cuántas entradas compró y cuánto gastó. Es una vista: no
-- guarda nada, se calcula cada vez que se consulta, así nunca queda desactualizada.
CREATE VIEW historial AS
SELECT p.id                                                            AS persona_id,
       COUNT(DISTINCT CASE WHEN e.asistente_id = p.id THEN e.evento_slug END) AS fechas,
       MIN(CASE WHEN e.asistente_id = p.id THEN ev.fecha END)          AS primera,
       MAX(CASE WHEN e.asistente_id = p.id THEN ev.fecha END)          AS ultima,
       SUM(e.comprador_id = p.id)                                      AS entradas_compradas,
       COALESCE(SUM(CASE WHEN e.comprador_id = p.id THEN e.precio END), 0) AS gastado
FROM personas p
JOIN entradas e ON p.id IN (e.comprador_id, e.asistente_id)
JOIN eventos ev ON ev.slug = e.evento_slug
GROUP BY p.id;
"""

MIGRACIONES = [V1, V2]


def conectar(ruta="crm.db"):
    conn = sqlite3.connect(ruta, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrar(conn)
    return conn


def migrar(conn):
    """Aplica las migraciones que la base todavía no tiene. Devuelve cuántas aplicó."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    pendientes = MIGRACIONES[version:]
    for numero, sql in enumerate(pendientes, start=version + 1):
        # Todo o nada: si una sentencia falla, la base queda en la versión anterior.
        try:
            conn.executescript(f"BEGIN; {sql} PRAGMA user_version = {numero}; COMMIT;")
        except sqlite3.Error:
            conn.rollback()
            raise
    return len(pendientes)


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
