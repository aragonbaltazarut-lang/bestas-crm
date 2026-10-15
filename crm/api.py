"""API HTTP: buscar personas, ver su historia, unir duplicados, bajas e incidencias.

Si existe la variable de entorno CRM_TOKEN, cada pedido tiene que traer el
encabezado `Authorization: Bearer <token>`. Sin la variable, la API queda abierta:
sirve para usarla en la propia compu, nunca en un servidor.
"""

import os
import secrets
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from .bajas import SIN_BAJA, dar_de_baja
from .db import conectar
from .personas import unir
from .reportes import REPORTES


def verificar_token(authorization: str | None = Header(None)):
    token = os.environ.get("CRM_TOKEN")
    if not token:
        return
    # compare_digest tarda lo mismo acierte o no: no deja adivinar el token de a una letra.
    if not authorization or not secrets.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(401, "Falta el token o no es el correcto")


app = FastAPI(title="CRM BESTAS", dependencies=[Depends(verificar_token)])


def get_conn():
    conn = conectar(os.environ.get("CRM_DB", "crm.db"))
    try:
        yield conn
    finally:
        conn.close()


class Union(BaseModel):
    se_va: int


class Baja(BaseModel):
    email: str
    motivo: str | None = None


@app.get("/personas")
def buscar_personas(
    buscar: str = "",
    fuente: str | None = None,
    genero: Literal["mujer", "hombre"] | None = None,
    tipo: Literal["persona", "organizacion"] | None = None,
    limite: int = Query(50, ge=1, le=500),
    desde: int = Query(0, ge=0),
    conn=Depends(get_conn),
):
    """Busca por nombre o mail y filtra por fuente, género o tipo. De a `limite` por página."""
    condiciones = ["(p.nombre LIKE ? OR p.email LIKE ?)"]
    parametros = [f"%{buscar}%", f"%{buscar}%"]
    if fuente:
        condiciones.append("EXISTS (SELECT 1 FROM origenes o WHERE o.persona_id = p.id AND o.fuente = ?)")
        parametros.append(fuente)
    for campo, valor in (("genero", genero), ("tipo", tipo)):
        if valor:
            condiciones.append(f"p.{campo} = ?")
            parametros.append(valor)
    donde = " AND ".join(condiciones)
    total = conn.execute(f"SELECT COUNT(*) FROM personas p WHERE {donde}", parametros).fetchone()[0]
    filas = conn.execute(
        f"SELECT * FROM personas p WHERE {donde} ORDER BY p.nombre LIMIT ? OFFSET ?",
        [*parametros, limite, desde],
    ).fetchall()
    return {"total": total, "desde": desde, "personas": [dict(f) for f in filas]}


@app.get("/personas/{persona_id}")
def ver_persona(persona_id: int, conn=Depends(get_conn)):
    """La ficha: datos, otros mails, de qué planillas salió, su historial en las fechas,
    qué entradas compró o usó y si se dio de baja."""
    fila = conn.execute(f"SELECT p.*, {SIN_BAJA} AS recibe_mails FROM personas p WHERE p.id = ?",
                        (persona_id,)).fetchone()
    if not fila:
        raise HTTPException(404, f"No existe la persona {persona_id}")
    alias = conn.execute("SELECT email FROM alias WHERE persona_id = ? ORDER BY email", (persona_id,))
    origenes = conn.execute(
        "SELECT fuente, detalle FROM origenes WHERE persona_id = ? ORDER BY fuente", (persona_id,)
    ).fetchall()
    historial = conn.execute(
        "SELECT fechas, primera, ultima, entradas_compradas, gastado FROM historial WHERE persona_id = ?",
        (persona_id,),
    ).fetchone()
    entradas = conn.execute(
        "SELECT ev.nombre AS evento, ev.fecha, e.tanda, e.precio, e.vendedor, "
        "e.comprador_id = :id AS compro, e.asistente_id = :id AS asistio "
        "FROM entradas e JOIN eventos ev ON ev.slug = e.evento_slug "
        "WHERE e.comprador_id = :id OR e.asistente_id = :id ORDER BY ev.fecha",
        {"id": persona_id},
    ).fetchall()
    return {
        **dict(fila),
        "recibe_mails": bool(fila["recibe_mails"]),
        "otros_mails": [a["email"] for a in alias],
        "origenes": [dict(o) for o in origenes],
        "historial": dict(historial) if historial else
            {"fechas": 0, "primera": None, "ultima": None, "entradas_compradas": 0, "gastado": 0},
        "entradas": [
            {**dict(e), "compro": bool(e["compro"]), "asistio": bool(e["asistio"])} for e in entradas
        ],
    }


@app.post("/personas/{persona_id}/unir")
def unir_personas(persona_id: int, union: Union, conn=Depends(get_conn)):
    """Une a esta persona la ficha `se_va`, que se borra. Ver `personas.unir`."""
    try:
        return unir(conn, persona_id, union.se_va)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get("/bajas")
def ver_bajas(conn=Depends(get_conn)):
    return [dict(f) for f in conn.execute("SELECT email, motivo, creada FROM bajas ORDER BY creada DESC")]


@app.post("/bajas")
def registrar_baja(baja: Baja, conn=Depends(get_conn)):
    """Da de baja un mail: no vuelve a salir en ninguna exportación."""
    try:
        return {"email": baja.email, "nueva": dar_de_baja(conn, baja.email, baja.motivo)}
    except ValueError as error:
        raise HTTPException(422, str(error))


@app.get("/incidencias")
def incidencias_abiertas(conn=Depends(get_conn)):
    filas = conn.execute("SELECT * FROM incidencias WHERE resuelta = 0 ORDER BY id").fetchall()
    return [dict(f) for f in filas]


@app.post("/incidencias/{incidencia_id}/resolver")
def resolver_incidencia(incidencia_id: int, conn=Depends(get_conn)):
    """Marca una incidencia como revisada a mano."""
    cursor = conn.execute("UPDATE incidencias SET resuelta = 1 WHERE id = ?", (incidencia_id,))
    if cursor.rowcount == 0:
        raise HTTPException(404, f"No existe la incidencia {incidencia_id}")
    conn.commit()
    return {"ok": True, "id": incidencia_id}


@app.get("/reportes")
def reportes(conn=Depends(get_conn)):
    return {titulo: [dict(f) for f in conn.execute(sql).fetchall()] for titulo, sql in REPORTES.items()}
