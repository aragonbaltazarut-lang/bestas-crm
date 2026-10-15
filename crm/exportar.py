"""Exportar un segmento a CSV: para mandar un mail o armar un público en Meta."""

import csv

from .bajas import SIN_BAJA


def segmento(conn, fuente=None, genero=None, compro=None, fechas=None):
    """Personas con mail, filtradas por fuente, género, si alguna vez compraron o a
    cuántas fechas fueron como mínimo. Nunca incluye a quien se dio de baja."""
    condiciones, parametros = ["p.email IS NOT NULL", SIN_BAJA], []
    if fuente:
        condiciones.append("EXISTS (SELECT 1 FROM origenes o WHERE o.persona_id = p.id AND o.fuente = ?)")
        parametros.append(fuente)
    if genero:
        condiciones.append("p.genero = ?")
        parametros.append(genero)
    if compro is not None:
        existe = "EXISTS (SELECT 1 FROM entradas e WHERE e.comprador_id = p.id)"
        condiciones.append(existe if compro else f"NOT {existe}")
    if fechas:
        condiciones.append("(SELECT h.fechas FROM historial h WHERE h.persona_id = p.id) >= ?")
        parametros.append(fechas)
    sql = f"SELECT p.nombre, p.email FROM personas p WHERE {' AND '.join(condiciones)} ORDER BY p.nombre"
    return conn.execute(sql, parametros).fetchall()


def a_csv(filas, ruta):
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["nombre", "email"])
        escritor.writerows(tuple(f) for f in filas)
    return len(filas)
