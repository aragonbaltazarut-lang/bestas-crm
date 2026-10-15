"""Alta y unificación de personas: la misma persona llega de varias planillas."""

from .db import ahora
from .enriquecer import CONFIANZA, es_organizacion, estimar_genero
from .normalizar import clave_email, esta_roto

CAMPOS = ("nombre", "dni", "telefono")


def buscar(conn, email=None, dni=None):
    """Busca por mail (con su clave: en Gmail, sin puntos), entre los principales y los
    alias; si no hay mail, por DNI."""
    if email:
        clave = clave_email(email)
        fila = conn.execute("SELECT * FROM personas WHERE email_clave = ?", (clave,)).fetchone()
        if fila:
            return fila
        fila = conn.execute(
            "SELECT p.* FROM alias a JOIN personas p ON p.id = a.persona_id WHERE a.email_clave = ?",
            (clave,),
        ).fetchone()
        if fila:
            return fila
    if dni:
        return conn.execute("SELECT * FROM personas WHERE dni = ?", (dni,)).fetchone()
    return None


def guardar(conn, *, email=None, nombre=None, dni=None, telefono=None,
            genero=None, genero_origen="declarado", notas=None):
    """Crea la persona o completa la que ya existe. Devuelve (id, es_nueva)."""
    if not email and not dni:
        raise ValueError("Hace falta un mail o un DNI para identificar a la persona")
    existente = buscar(conn, email, dni)

    if existente is None:
        organizacion = es_organizacion(nombre, email)
        por_nombre = None if organizacion else estimar_genero(nombre)
        if not genero:
            genero, genero_origen = por_nombre, "nombre"
        conn.execute(
            "INSERT INTO personas (email, email_clave, nombre, tipo, dni, telefono, genero, "
            "genero_origen, genero_por_nombre, notas, creada, actualizada) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (email, clave_email(email), nombre or email or dni,
             "organizacion" if organizacion else "persona", dni, telefono,
             genero, genero_origen if genero else None, por_nombre, notas, ahora(), ahora()),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0], True

    completar(conn, existente, email=email, nombre=nombre, dni=dni, telefono=telefono,
              genero=genero, genero_origen=genero_origen, notas=notas)
    return existente["id"], False


def completar(conn, existente, *, email=None, nombre=None, dni=None, telefono=None,
              genero=None, genero_origen="declarado", notas=None):
    """Suma a una persona lo que llega de otra planilla (o de otra ficha, al unir).

    Un dato que ya estaba no se pisa con otro distinto: solo se completan los
    vacíos. Las excepciones: un nombre con caracteres rotos se reemplaza cuando
    llega la versión sana, y un género se reemplaza por otro de una fuente más
    confiable (lo declarado en la ticketera pisa a lo estimado por el nombre).
    Las notas se suman.
    """
    nuevos = {"nombre": nombre, "dni": dni, "telefono": telefono}
    cambios = {}
    for campo in CAMPOS:
        valor = nuevos[campo]
        if not valor:
            continue
        actual = existente[campo]
        if campo == "nombre" and actual in (existente["email"], existente["dni"]):
            actual = None  # se había guardado el mail como nombre porque no había otro
        if not actual or (campo == "nombre" and esta_roto(actual) and not esta_roto(valor)):
            cambios[campo] = valor
    if "nombre" in cambios and existente["tipo"] == "persona":
        cambios["genero_por_nombre"] = estimar_genero(cambios["nombre"])
        if not genero:
            genero, genero_origen = cambios["genero_por_nombre"], "nombre"
    if genero and CONFIANZA[genero_origen] > CONFIANZA.get(existente["genero_origen"], 0):
        cambios["genero"], cambios["genero_origen"] = genero, genero_origen
    if notas and notas not in (existente["notas"] or ""):
        cambios["notas"] = "; ".join(filter(None, [existente["notas"], notas]))
    if email and not existente["email"]:
        cambios["email"], cambios["email_clave"] = email, clave_email(email)
    if cambios:
        asignaciones = ", ".join(f"{c} = ?" for c in cambios)
        conn.execute(
            f"UPDATE personas SET {asignaciones}, actualizada = ? WHERE id = ?",
            (*cambios.values(), ahora(), existente["id"]),
        )


def unir(conn, queda_id, se_va_id):
    """Une dos fichas que son la misma persona: la segunda pasa a la primera y se borra.

    Es para los casos del reporte "Posibles duplicados", que el CRM no une solo.
    Las entradas, los orígenes y los alias pasan a la que queda; sus datos completan
    los vacíos con las mismas reglas que una importación; y su mail queda como
    alias de la que queda, así reimportar una planilla no la vuelve a crear. La
    unión queda registrada en `uniones`. Todo o nada: si algo falla, no cambia nada.
    """
    if queda_id == se_va_id:
        raise ValueError("Una persona no se puede unir consigo misma")
    fichas = {}
    for persona_id in (queda_id, se_va_id):
        fichas[persona_id] = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
        if fichas[persona_id] is None:
            raise LookupError(f"No existe la persona {persona_id}")
    queda, se_va = fichas[queda_id], fichas[se_va_id]

    with conn:  # una transacción: se confirma al final, o se deshace si hay un error
        conn.execute("UPDATE entradas SET comprador_id = ? WHERE comprador_id = ?", (queda_id, se_va_id))
        conn.execute("UPDATE entradas SET asistente_id = ? WHERE asistente_id = ?", (queda_id, se_va_id))
        conn.execute(
            "INSERT OR IGNORE INTO origenes (persona_id, fuente, detalle) "
            "SELECT ?, fuente, detalle FROM origenes WHERE persona_id = ?",
            (queda_id, se_va_id),
        )
        conn.execute("DELETE FROM origenes WHERE persona_id = ?", (se_va_id,))
        conn.execute("UPDATE alias SET persona_id = ? WHERE persona_id = ?", (queda_id, se_va_id))
        conn.execute("DELETE FROM personas WHERE id = ?", (se_va_id,))
        # Si la que queda no tenía mail, toma el de la otra; si tenía, el de la otra es un alias.
        if se_va["email"] and queda["email"] and se_va["email_clave"] != queda["email_clave"]:
            conn.execute(
                "INSERT OR IGNORE INTO alias (email_clave, email, persona_id) VALUES (?, ?, ?)",
                (se_va["email_clave"], se_va["email"], queda_id),
            )
        completar(
            conn, queda, email=se_va["email"],
            nombre=None if se_va["nombre"] in (se_va["email"], se_va["dni"]) else se_va["nombre"],
            dni=se_va["dni"], telefono=se_va["telefono"], genero=se_va["genero"],
            genero_origen=se_va["genero_origen"] or "nombre", notas=se_va["notas"],
        )
        conn.execute(
            "INSERT INTO uniones (queda_id, se_va_id, se_va_nombre, se_va_email, creada) "
            "VALUES (?, ?, ?, ?, ?)",
            (queda_id, se_va_id, se_va["nombre"], se_va["email"], ahora()),
        )
    return {"queda": queda["nombre"], "se_va": se_va["nombre"]}


def anotar_origen(conn, persona_id, fuente, detalle):
    conn.execute(
        "INSERT OR IGNORE INTO origenes (persona_id, fuente, detalle) VALUES (?, ?, ?)",
        (persona_id, fuente, detalle),
    )


def anotar_incidencia(conn, fuente, ubicacion, tipo, detalle):
    """Una incidencia por celda y tipo: reimportar la misma planilla no las duplica."""
    conn.execute(
        "INSERT OR IGNORE INTO incidencias (fuente, ubicacion, tipo, detalle, creada) "
        "VALUES (?, ?, ?, ?, ?)",
        (fuente, ubicacion, tipo, detalle, ahora()),
    )
