"""Reportes del CRM, escritos en SQL."""

POR_FUENTE = """
SELECT fuente, COUNT(DISTINCT persona_id) AS personas
FROM origenes
GROUP BY fuente
ORDER BY personas DESC
"""

# Lo que ninguna planilla sola puede decir: quién aparece en más de una.
EN_VARIAS_FUENTES = """
SELECT p.nombre, p.email, GROUP_CONCAT(DISTINCT o.fuente) AS fuentes
FROM personas p
JOIN origenes o ON o.persona_id = p.id
GROUP BY p.id
HAVING COUNT(DISTINCT o.fuente) > 1
ORDER BY p.nombre
"""

MEJORES_COMPRADORES = """
SELECT p.nombre, p.email,
       COUNT(*)                         AS entradas,
       SUM(e.asistente_id IS NOT p.id)  AS para_otros,
       ROUND(SUM(e.precio))             AS gastado
FROM entradas e
JOIN personas p ON p.id = e.comprador_id
GROUP BY p.id
ORDER BY gastado DESC
LIMIT 10
"""

VENTAS_POR_TANDA = """
SELECT ev.nombre AS evento, e.tanda,
       COUNT(*)              AS entradas,
       ROUND(SUM(e.precio))  AS recaudado
FROM entradas e
JOIN eventos ev ON ev.slug = e.evento_slug
GROUP BY ev.slug, e.tanda
ORDER BY ev.fecha, e.tanda
"""

# Lo que vendió cada RRPP en cada fecha, y a cuántas personas distintas.
VENTAS_POR_VENDEDOR = """
SELECT ev.nombre AS evento,
       COALESCE(e.vendedor, 'sin dato')  AS vendedor,
       COUNT(*)                          AS entradas,
       COUNT(DISTINCT e.comprador_id)    AS compradores,
       ROUND(SUM(e.precio))              AS recaudado
FROM entradas e
JOIN eventos ev ON ev.slug = e.evento_slug
GROUP BY ev.slug, e.vendedor
ORDER BY ev.fecha, recaudado DESC
"""

# El público que vuelve: tuvo entrada en más de una fecha.
PUBLICO_QUE_VOLVIO = """
SELECT p.nombre, p.email, h.fechas, h.primera, h.ultima, h.gastado
FROM historial h
JOIN personas p ON p.id = h.persona_id
WHERE h.fechas > 1
ORDER BY h.fechas DESC, h.ultima DESC
"""

POR_GENERO = """
SELECT COALESCE(genero, 'sin dato')          AS genero,
       COALESCE(genero_origen, '-')          AS origen,
       COUNT(*)                              AS personas
FROM personas
WHERE tipo = 'persona'
GROUP BY genero, genero_origen
ORDER BY genero IS NULL, genero, personas DESC
"""

# El género elegido (de la ticketera o del título de la columna) no coincide con el
# que dice el nombre: o la planilla se equivocó, o el nombre engaña. Se revisa a mano.
GENERO_A_REVISAR = """
SELECT nombre, email, genero, genero_origen AS origen, genero_por_nombre AS por_nombre
FROM personas
WHERE genero_por_nombre IS NOT NULL AND genero != genero_por_nombre
ORDER BY nombre
"""

ORGANIZACIONES = """
SELECT nombre, email
FROM personas
WHERE tipo = 'organizacion'
ORDER BY nombre
"""

# Mismo nombre con otro mail: puede ser la misma persona. No se unen solas: se revisan
# y, si son la misma, se unen con `python -m crm unir <id que queda> <id que se va>`.
POSIBLES_DUPLICADOS = """
SELECT LOWER(nombre) AS nombre, COUNT(*) AS veces,
       GROUP_CONCAT(id, ', ') AS ids, GROUP_CONCAT(email, ', ') AS mails
FROM personas
WHERE tipo = 'persona' AND nombre LIKE '% %' AND nombre NOT LIKE '%@%'
GROUP BY LOWER(nombre)
HAVING COUNT(*) > 1
ORDER BY veces DESC, nombre
"""

INCIDENCIAS_ABIERTAS = """
SELECT fuente, ubicacion, tipo, detalle
FROM incidencias
WHERE resuelta = 0
ORDER BY fuente, tipo, id
"""

BAJAS = """
SELECT email, COALESCE(motivo, '') AS motivo, SUBSTR(creada, 1, 10) AS fecha
FROM bajas
ORDER BY creada DESC
"""

REPORTES = {
    "Personas por fuente": POR_FUENTE,
    "Personas en más de una fuente": EN_VARIAS_FUENTES,
    "Público que volvió": PUBLICO_QUE_VOLVIO,
    "Mejores compradores": MEJORES_COMPRADORES,
    "Ventas por tanda": VENTAS_POR_TANDA,
    "Ventas por vendedor": VENTAS_POR_VENDEDOR,
    "Personas por género": POR_GENERO,
    "Género a revisar": GENERO_A_REVISAR,
    "Organizaciones": ORGANIZACIONES,
    "Posibles duplicados": POSIBLES_DUPLICADOS,
    "Bajas": BAJAS,
    "Incidencias abiertas": INCIDENCIAS_ABIERTAS,
}


def tabla(conn, sql):
    """Corre la consulta y la devuelve como texto en columnas."""
    cursor = conn.execute(sql)
    columnas = [c[0] for c in cursor.description]
    filas = [[("" if v is None else str(v)) for v in fila] for fila in cursor.fetchall()]
    if not filas:
        return "(sin datos)"
    anchos = [max(len(c), *(len(f[i]) for f in filas)) for i, c in enumerate(columnas)]
    linea = lambda valores: "  ".join(v.ljust(a) for v, a in zip(valores, anchos))
    return "\n".join([linea(columnas), linea(["-" * a for a in anchos]), *map(linea, filas)])
