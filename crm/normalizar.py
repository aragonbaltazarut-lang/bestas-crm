"""Limpieza de los datos tal como vienen de las planillas."""

import difflib
import re
import unicodedata

ROTO = "\ufffd"  # el rombo con un signo de pregunta que queda cuando una ñ o un acento se guardó con otra codificación

PATRON_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")
# Los dominios que más aparecen, para reconocer uno mal escrito ('gmail.con').
# Los que están acá son válidos tal cual: 'hotmail.com.ar' existe, 'gmail.com.ar' no.
DOMINIOS_CONOCIDOS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.com.ar", "hotmail.es",
    "outlook.com", "outlook.com.ar", "outlook.es", "live.com", "live.com.ar",
    "yahoo.com", "yahoo.com.ar", "yahoo.es", "ymail.com", "icloud.com", "me.com",
    "mail.com", "email.com", "gmx.com", "aol.com", "protonmail.com", "proton.me", "fibertel.com.ar",
}
DOMINIOS_INEXISTENTES = {"gmail.com.ar": "gmail.com", "gmail.es": "gmail.com"}
PARTICULAS = {"de", "del", "la", "las", "los", "y", "da", "van", "von"}
GENEROS = {
    "female": "mujer", "mujer": "mujer", "f": "mujer",
    "male": "hombre", "hombre": "hombre", "m": "hombre",
}


def texto(valor):
    """Cualquier celda a texto sin espacios de más; vacío pasa a None."""
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)  # Excel guarda los DNI como 40123456.0
    limpio = " ".join(str(valor).split())
    return limpio or None


def email(valor):
    """Devuelve el mail normalizado, o None si no es un mail."""
    return email_corregido(valor)[0]


def email_corregido(valor):
    """(mail normalizado, True si hubo que corregir el dominio), o (None, False).

    'ana@gmail.con' -> ('ana@gmail.com', True). Solo corrige contra los dominios
    más comunes y cuando el parecido es muy alto, para no inventar un mail.
    """
    limpio = texto(valor)
    if not limpio:
        return None, False
    limpio = limpio.replace(" ", "").lower()
    if not PATRON_EMAIL.fullmatch(limpio):
        return None, False
    local, dominio = limpio.split("@")
    if dominio in DOMINIOS_CONOCIDOS:
        return limpio, False
    corregido = DOMINIOS_INEXISTENTES.get(dominio)
    if not corregido and dominio.startswith("gmail.com"):
        corregido = "gmail.com"  # 'gmail.comjuanperez': algo pegado después del dominio
    base, _, pais = dominio.rpartition(".")
    if not corregido and len(pais) == 2 and base in DOMINIOS_CONOCIDOS:
        return limpio, False  # el mismo proveedor en otro país: 'yahoo.com.br' no es 'yahoo.com.ar'
    if not corregido:
        parecidos = difflib.get_close_matches(dominio, DOMINIOS_CONOCIDOS, n=1, cutoff=0.88)
        corregido = parecidos[0] if parecidos else None
    return (f"{local}@{corregido}", True) if corregido else (limpio, False)


def clave_email(mail):
    """La forma con la que se compara si dos mails son el mismo.

    Gmail ignora los puntos y lo que va después de un '+': juan.perez+bestas@gmail.com
    y juanperez@gmail.com llegan a la misma casilla.
    """
    if not mail:
        return None
    local, dominio = mail.split("@")
    if dominio in ("gmail.com", "googlemail.com"):
        local = local.split("+")[0].replace(".", "")
        dominio = "gmail.com"
    return f"{local}@{dominio}"


def sin_tildes(valor):
    return "".join(
        c for c in unicodedata.normalize("NFD", valor) if unicodedata.category(c) != "Mn"
    )


def separar_nota(valor):
    """'Ana Pérez (BOMBO) 👑' -> ('Ana Pérez', 'BOMBO').

    En las listas de RRPP el nombre trae pegado quién lo trajo o de dónde viene:
    entre paréntesis (a veces sin cerrar), después de una barra vertical, o el
    rol mismo: 'Juan Pérez RRPP CROBAR' -> ('Juan Pérez', 'RRPP CROBAR').
    """
    limpio = texto(valor)
    if not limpio:
        return None, None
    limpio, *despues_de_barra = limpio.split("|")
    notas = [texto(m) for m in re.findall(r"\(([^)]*)\)?", limpio)] + despues_de_barra
    limpio = re.sub(r"\([^)]*\)?", " ", limpio)
    rol = re.search(r"\brrpp\b.*$", limpio, flags=re.IGNORECASE)
    if rol and rol.start() > 0:
        notas.insert(0, "RRPP" + rol.group()[4:])
        limpio = limpio[: rol.start()]
    return _sin_simbolos(limpio), "; ".join(filter(None, map(_sin_simbolos, notas))) or None


def _sin_simbolos(valor):
    """Saca emojis y marcas (👑, ™, ®) y unifica los apóstrofos: D´Angelo -> D'Angelo."""
    limpio = unicodedata.normalize("NFC", valor).replace("´", "'").replace("’", "'")
    return texto("".join(
        c for c in limpio if unicodedata.category(c)[0] not in "SC" and c != "\ufe0f"
    ))


def mails(valor):
    """Los mails válidos de una celda: a veces vienen dos, 'a@x.com // b@x.com'."""
    partes = re.split(r"\s*(?://|;|,|\s/\s)\s*", texto(valor) or "")
    return [m for m in map(email, partes) if m]


def nombre(*partes):
    """Une nombre y apellido y arregla las mayúsculas: 'lulii ejemplo' -> 'Lulii Ejemplo'."""
    completo = texto(" ".join(p for p in map(texto, partes) if p))
    completo = completo.strip(" :;,.-") if completo else None  # 'Florencia Pérez:' en una lista copiada
    if not completo:
        return None
    if completo.isupper():
        completo = completo.lower()
    palabras = []
    for i, palabra in enumerate(completo.split(" ")):
        if i > 0 and palabra.lower() in PARTICULAS:
            palabras.append(palabra.lower())
        elif palabra.islower():
            palabras.append(palabra[0].upper() + palabra[1:])
        else:
            palabras.append(palabra)  # 'DeMuestra' o 'McAllister' se respetan
    return " ".join(palabras)


def esta_roto(valor):
    return valor is not None and ROTO in valor


def genero(valor):
    limpio = texto(valor)
    return GENEROS.get(limpio.lower()) if limpio else None


def dni(valor):
    limpio = texto(valor)
    if not limpio:
        return None
    digitos = re.sub(r"\D", "", limpio)
    return digitos if 6 <= len(digitos) <= 9 else None


def telefono(valor):
    limpio = texto(valor)
    if not limpio:
        return None
    digitos = re.sub(r"\D", "", limpio)
    return ("+" if limpio.startswith("+") else "") + digitos if digitos else None
