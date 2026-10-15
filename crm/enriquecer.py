"""Datos que no vienen en las planillas pero se pueden deducir: género y tipo de contacto.

Todo se calcula acá mismo, sin mandar nombres a servicios de afuera: son
datos personales de terceros.
"""

import csv
import re
from functools import cache
from pathlib import Path

from .normalizar import sin_tildes

# De dónde salió el género, de más confiable a menos. Un dato más confiable
# reemplaza a uno menos confiable, nunca al revés.
CONFIANZA = {"declarado": 3, "lista": 2, "nombre": 1}

PALABRAS_DE_ORGANIZACION = {
    "agencia", "bar", "booking", "club", "data", "embajadoras", "eventos", "fiestas",
    "group", "info", "management", "marketing", "prensa", "producciones", "productora",
    "records", "studio",
}
CASILLAS_GENERICAS = re.compile(
    r"(info|hola|contacto|prensa|eventos?|marketing|admin|ventas|booking|management|rrpp|press)\d*"
)


@cache
def diccionario():
    """{nombre de pila: 'mujer' | 'hombre' | 'ambiguo'}, de nombres.csv."""
    ruta = Path(__file__).with_name("nombres.csv")
    with open(ruta, encoding="utf-8") as archivo:
        filas = csv.DictReader(linea for linea in archivo if not linea.startswith("#"))
        return {fila["nombre"]: fila["genero"] for fila in filas}


def nombre_de_pila(nombre, tildes=False):
    """'María José Pérez' -> 'maria' (o 'maría' con tildes=True), en minúscula."""
    if not nombre or "@" in nombre:
        return None
    primero = re.split(r"[\s/]+", nombre.strip())[0].lower().strip(".'-")
    return (primero if tildes else sin_tildes(primero)) or None


def estimar_genero(nombre):
    """El género más probable por el nombre de pila, o None si no se sabe o es ambiguo.

    Primero busca el nombre con tildes ('josé'), y si no está, sin tildes.
    """
    nombres = diccionario()
    genero = nombres.get(nombre_de_pila(nombre, tildes=True)) or nombres.get(nombre_de_pila(nombre))
    return genero if genero in ("mujer", "hombre") else None


def es_organizacion(nombre, email):
    """Una productora, un medio o una casilla genérica, no una persona."""
    palabras = set(re.findall(r"[a-z]+", sin_tildes(nombre or "").lower()))
    if palabras & PALABRAS_DE_ORGANIZACION:
        return True
    if nombre and re.search(r"\.(com|ar|net|org)\b", nombre.lower()):
        return True  # el nombre es una web: 'ahivamos.com'
    # hola@ o info@ es de una organización, salvo que el nombre sea de una persona:
    # un DJ con su propio dominio sigue siendo una persona.
    local = (email or "").split("@")[0]
    return bool(CASILLAS_GENERICAS.fullmatch(local)) and estimar_genero(nombre) is None


def recalcular(conn):
    """Vuelve a estimar tipo y género de toda la base; los datos declarados no se tocan.

    Sirve después de sumar nombres a nombres.csv: no hace falta reimportar.
    """
    resumen = {"organizaciones": 0, "género estimado": 0}
    for persona in conn.execute("SELECT id, nombre, email, genero_origen FROM personas").fetchall():
        organizacion = es_organizacion(persona["nombre"], persona["email"])
        por_nombre = None if organizacion else estimar_genero(persona["nombre"])
        conn.execute(
            "UPDATE personas SET tipo = ?, genero_por_nombre = ? WHERE id = ?",
            ("organizacion" if organizacion else "persona", por_nombre, persona["id"]),
        )
        resumen["organizaciones"] += organizacion
        if persona["genero_origen"] in ("declarado", "lista"):
            continue
        conn.execute(
            "UPDATE personas SET genero = ?, genero_origen = ? WHERE id = ?",
            (por_nombre, "nombre" if por_nombre else None, persona["id"]),
        )
        resumen["género estimado"] += por_nombre is not None
    conn.commit()
    return resumen
