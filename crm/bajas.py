"""La lista de bajas: quien pidió no recibir más mails no vuelve a entrar en un envío.

Funciona como la lista de supresión de los servicios de mailing: la baja es de la
casilla, no de la ficha. Reimportar una planilla donde esa casilla aparece no la
vuelve a sumar, y si la persona tiene más de un mail (un alias), la baja de
cualquiera de los dos la saca de los envíos.
"""

from .db import ahora
from .normalizar import clave_email, email as normalizar_email


def dar_de_baja(conn, email, motivo=None):
    """Registra la baja de un mail. Devuelve False si ya estaba dado de baja."""
    mail = normalizar_email(email)
    if not mail:
        raise ValueError(f"No es un mail: {email!r}")
    cursor = conn.execute(
        "INSERT OR IGNORE INTO bajas (email_clave, email, motivo, creada) VALUES (?, ?, ?, ?)",
        (clave_email(mail), mail, motivo, ahora()),
    )
    conn.commit()
    return cursor.rowcount == 1


# Para sumar a un WHERE sobre `personas p`: la persona no tiene ningún mail dado de baja.
SIN_BAJA = """NOT EXISTS (
    SELECT 1 FROM bajas b
    WHERE b.email_clave = p.email_clave
       OR b.email_clave IN (SELECT a.email_clave FROM alias a WHERE a.persona_id = p.id)
)"""
