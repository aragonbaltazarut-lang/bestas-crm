import pytest
from openpyxl import Workbook

from crm.db import conectar
from crm.importar import importar_bombo, importar_lista
from crm.personas import guardar
from scripts.generar_ejemplos import bombo, clientes, lista


@pytest.fixture
def conn(tmp_path):
    conexion = conectar(tmp_path / "test.db")
    yield conexion
    conexion.close()


def persona(conn, email):
    return conn.execute("SELECT * FROM personas WHERE email = ?", (email,)).fetchone()


def tipos_de_incidencia(conn):
    return sorted(f["tipo"] for f in conn.execute("SELECT tipo FROM incidencias"))


# ---------------------------------------------------------------- Bombo

def test_bombo_carga_entradas_y_personas(conn, tmp_path):
    resumen = importar_bombo(conn, bombo(tmp_path), "Evento Ejemplo", "2026-05-16")
    assert resumen == {"entradas": 6, "personas nuevas": 5, "incidencias": 1}
    carla = persona(conn, "carla.inventada@example.com")
    assert carla["nombre"] == "Carla Inventada"
    assert carla["dni"] == "41222333"
    assert carla["genero"] == "mujer"


def test_bombo_la_entrada_pasada_a_otro_queda_a_nombre_de_los_dos(conn, tmp_path):
    importar_bombo(conn, bombo(tmp_path), "Evento Ejemplo", "2026-05-16")
    entrada = conn.execute("SELECT * FROM entradas WHERE id = 'ejemplo0002'").fetchone()
    ana = persona(conn, "ana.ejemplo@example.com")
    bruno = persona(conn, "bruno.prueba@example.com")
    assert entrada["comprador_id"] == ana["id"]
    assert entrada["asistente_id"] == bruno["id"]
    assert bruno["genero"] == "hombre"


def test_bombo_asistente_sin_mail_queda_como_incidencia(conn, tmp_path):
    importar_bombo(conn, bombo(tmp_path), "Evento Ejemplo", "2026-05-16")
    entrada = conn.execute("SELECT * FROM entradas WHERE id = 'ejemplo0005'").fetchone()
    assert entrada["asistente_id"] is None
    assert tipos_de_incidencia(conn) == ["asistente sin mail"]


def test_bombo_se_puede_importar_dos_veces(conn, tmp_path):
    ruta = bombo(tmp_path)
    importar_bombo(conn, ruta, "Evento Ejemplo", "2026-05-16")
    segunda = importar_bombo(conn, ruta, "Evento Ejemplo", "2026-05-16")
    assert segunda["personas nuevas"] == 0
    assert conn.execute("SELECT COUNT(*) FROM entradas").fetchone()[0] == 6
    assert conn.execute("SELECT COUNT(*) FROM incidencias").fetchone()[0] == 1


def test_bombo_rechaza_una_planilla_que_no_es_de_bombo(conn, tmp_path):
    libro = Workbook()
    libro.active.append(["Nombre", "Mail"])
    ruta = tmp_path / "otra.xlsx"
    libro.save(ruta)
    with pytest.raises(ValueError, match="Buyer Email"):
        importar_bombo(conn, ruta, "Evento Ejemplo", "2026-05-16")


# ---------------------------------------------------------------- listas sueltas

def test_lista_encuentra_los_pares_de_nombre_y_mail(conn, tmp_path):
    resumen = importar_lista(conn, lista(tmp_path), "Lista Ejemplo")
    assert resumen == {"contactos": 6, "personas nuevas": 5, "repetidos": 1, "incidencias": 2}
    assert persona(conn, "lucia.demo@example.com")["nombre"] == "Lucía Demo"
    assert persona(conn, "tomas.ficticio@example.com")["nombre"] == "Tomás Ficticio"


def test_lista_usa_el_titulo_de_la_columna(conn, tmp_path):
    importar_lista(conn, lista(tmp_path), "Lista Ejemplo")
    florencia = persona(conn, "florencia.prueba@example.com")
    tomas = persona(conn, "tomas.ficticio@example.com")
    assert (florencia["genero"], florencia["genero_origen"]) == ("mujer", "lista")
    # La columna de los hombres no tiene título: el género sale del nombre, y queda dicho.
    assert (tomas["genero"], tomas["genero_origen"]) == ("hombre", "nombre")
    origen = conn.execute("SELECT detalle FROM origenes WHERE persona_id = ?", (florencia["id"],)).fetchone()
    assert origen["detalle"] == "columna mujeres"


def test_lista_anota_lo_que_no_pudo_cargar(conn, tmp_path):
    importar_lista(conn, lista(tmp_path), "Lista Ejemplo")
    assert tipos_de_incidencia(conn) == ["mail inválido", "nombre sin mail"]
    ubicaciones = {f["ubicacion"] for f in conn.execute("SELECT ubicacion FROM incidencias")}
    assert ubicaciones == {"F7", "N9"}


def test_lista_lee_todas_las_hojas_y_la_columna_de_dni(conn, tmp_path):
    resumen = importar_lista(conn, clientes(tmp_path), "Clientes Ejemplo")
    assert resumen == {"contactos": 5, "personas nuevas": 5, "repetidos": 0, "incidencias": 3}
    hernan = persona(conn, "hernan.muestra@example.com")
    assert hernan["nombre"] == "Hernán de la Muestra"
    assert hernan["dni"] == "45555666"
    origen = conn.execute("SELECT detalle FROM origenes WHERE persona_id = ?", (hernan["id"],)).fetchone()
    assert origen["detalle"] == "hoja CLIENTES"


def test_lista_guarda_lo_que_venia_pegado_al_nombre(conn, tmp_path):
    importar_lista(conn, clientes(tmp_path), "Clientes Ejemplo")
    gabriela = persona(conn, "gabriela.ensayo@example.com")
    assert (gabriela["nombre"], gabriela["notas"]) == ("Gabriela Ensayo", "BOMBO")
    carla = persona(conn, "carla.inventada@example.com")
    assert carla["notas"] == "otro mail: carla.otra@example.com"


def test_lista_no_toma_encabezados_ni_notas_como_nombres(conn, tmp_path):
    importar_lista(conn, clientes(tmp_path), "Clientes Ejemplo")
    incidencias = {f["ubicacion"]: f["detalle"] for f in conn.execute("SELECT * FROM incidencias")}
    assert incidencias == {
        "RRPP!A3": "Medio Ejemplo (al lado: no comisiona)",
        "CLIENTES!A3": "IGNACIO SIN MAIL",
        "CLIENTES!A5": "Venta en puerta (al lado: -)",
    }


# ---------------------------------------------------------------- cruce

def test_la_misma_persona_en_dos_planillas_es_una_sola(conn, tmp_path):
    importar_bombo(conn, bombo(tmp_path), "Evento Ejemplo", "2026-05-16")
    resumen = importar_lista(conn, lista(tmp_path), "Lista Ejemplo")
    assert resumen["personas nuevas"] == 2  # Ana, Lucía y Bruno ya estaban
    ana = persona(conn, "ana.ejemplo@example.com")
    fuentes = {f["fuente"] for f in conn.execute("SELECT fuente FROM origenes WHERE persona_id = ?", (ana["id"],))}
    assert fuentes == {"Bombo · Evento Ejemplo", "Lista Ejemplo"}


def test_lo_declarado_pisa_a_lo_estimado_y_no_al_reves(conn):
    persona_id, _ = guardar(conn, email="x@example.com", nombre="Alex Ejemplo")
    assert conn.execute("SELECT genero FROM personas").fetchone()["genero"] is None  # ambiguo
    guardar(conn, email="x@example.com", genero="mujer", genero_origen="declarado")
    guardar(conn, email="x@example.com", genero="hombre", genero_origen="nombre")
    fila = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
    assert (fila["genero"], fila["genero_origen"]) == ("mujer", "declarado")


def test_gmail_ignora_puntos_y_mas(conn):
    primero, _ = guardar(conn, email="juan.ejemplo@gmail.com", nombre="Juan Ejemplo")
    segundo, nueva = guardar(conn, email="juanejemplo+bestas@gmail.com", nombre="Juan Ejemplo")
    assert (segundo, nueva) == (primero, False)


def test_mail_con_dominio_mal_escrito_se_corrige_y_se_anota(conn, tmp_path):
    libro = Workbook()
    libro.active.append(["Ana Ejemplo", "ana.ejemplo@gmail.con"])
    ruta = tmp_path / "typo.xlsx"
    libro.save(ruta)
    importar_lista(conn, ruta, "Typo")
    assert persona(conn, "ana.ejemplo@gmail.com") is not None
    assert tipos_de_incidencia(conn) == ["mail corregido"]


def test_una_organizacion_no_lleva_genero(conn):
    guardar(conn, email="info@example.com", nombre="Tienda Ejemplo")
    guardar(conn, email="fiestas@example.com", nombre="Fiestas Ejemplo")
    filas = conn.execute("SELECT tipo, genero FROM personas").fetchall()
    assert [tuple(f) for f in filas] == [("organizacion", None), ("organizacion", None)]


def test_un_nombre_real_reemplaza_al_mail_que_hacia_de_nombre(conn):
    persona_id, _ = guardar(conn, email="lucia@example.com")
    guardar(conn, email="lucia@example.com", nombre="Lucía Ejemplo")
    fila = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
    assert (fila["nombre"], fila["genero"]) == ("Lucía Ejemplo", "mujer")


def test_un_dato_no_se_pisa_pero_un_nombre_roto_si(conn):
    persona_id, _ = guardar(conn, email="x@example.com", nombre="Sofía Pe\ufffda", dni="40111222")
    guardar(conn, email="x@example.com", nombre="Sofía Peña", dni="99999999")
    fila = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
    assert fila["nombre"] == "Sofía Peña"
    assert fila["dni"] == "40111222"


def test_el_genero_que_choca_con_el_nombre_queda_para_revisar(conn):
    from crm.reportes import GENERO_A_REVISAR

    guardar(conn, email="juan@example.com", nombre="Juan Ejemplo", genero="mujer", genero_origen="lista")
    guardar(conn, email="ana@example.com", nombre="Ana Ejemplo", genero="mujer", genero_origen="lista")
    filas = conn.execute(GENERO_A_REVISAR).fetchall()
    assert [(f["nombre"], f["genero"], f["por_nombre"]) for f in filas] == [("Juan Ejemplo", "mujer", "hombre")]
