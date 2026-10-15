import pytest

from crm.bajas import dar_de_baja
from crm.db import conectar
from crm.exportar import segmento
from crm.importar import importar_bombo, importar_lista
from crm.personas import guardar, unir
from scripts.generar_ejemplos import bombo, lista


@pytest.fixture
def conn(tmp_path):
    conexion = conectar(tmp_path / "test.db")
    yield conexion
    conexion.close()


def mails(filas):
    return {f["email"] for f in filas}


def contar(conn, tabla):
    return conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


# ---------------------------------------------------------------- bajas

def test_una_baja_sale_de_todas_las_exportaciones(conn, tmp_path):
    importar_lista(conn, lista(tmp_path), "Lista Ejemplo")
    assert "ana.ejemplo@example.com" in mails(segmento(conn))
    assert dar_de_baja(conn, "Ana.Ejemplo@Example.com", "lo pidió por Instagram")
    assert "ana.ejemplo@example.com" not in mails(segmento(conn))
    assert "ana.ejemplo@example.com" not in mails(segmento(conn, genero="mujer"))


def test_la_baja_sigue_aunque_se_reimporte(conn, tmp_path):
    ruta = lista(tmp_path)
    importar_lista(conn, ruta, "Lista Ejemplo")
    dar_de_baja(conn, "ana.ejemplo@example.com")
    importar_lista(conn, ruta, "Lista Ejemplo")
    assert "ana.ejemplo@example.com" not in mails(segmento(conn))


def test_la_baja_va_por_la_casilla_no_por_como_se_escribio(conn):
    guardar(conn, email="juan.ejemplo@gmail.com", nombre="Juan Ejemplo")
    dar_de_baja(conn, "juanejemplo+promo@gmail.com")  # en Gmail es la misma casilla
    assert segmento(conn) == []


def test_dar_de_baja_dos_veces_no_duplica(conn):
    assert dar_de_baja(conn, "ana@example.com")
    assert not dar_de_baja(conn, "ana@example.com")
    assert contar(conn, "bajas") == 1


def test_no_se_da_de_baja_algo_que_no_es_un_mail(conn):
    with pytest.raises(ValueError):
        dar_de_baja(conn, "ana sin arroba")


# ---------------------------------------------------------------- unir

def dos_fichas_de_ana(conn, tmp_path):
    """Ana compró en Bombo con un mail y está en una lista con otro."""
    importar_bombo(conn, bombo(tmp_path), "Evento Ejemplo", "2026-05-16")
    queda = conn.execute("SELECT * FROM personas WHERE email = 'ana.ejemplo@example.com'").fetchone()
    se_va, _ = guardar(conn, email="ana.otra@example.com", nombre="Ana Ejemplo", telefono="+5491100000000")
    conn.execute("INSERT INTO origenes VALUES (?, 'Lista Ejemplo', 'sin título')", (se_va,))
    return queda["id"], se_va


def test_unir_pasa_todo_a_la_ficha_que_queda(conn, tmp_path):
    queda, se_va = dos_fichas_de_ana(conn, tmp_path)
    unir(conn, queda, se_va)
    assert conn.execute("SELECT * FROM personas WHERE id = ?", (se_va,)).fetchone() is None
    ana = conn.execute("SELECT * FROM personas WHERE id = ?", (queda,)).fetchone()
    assert ana["telefono"] == "+5491100000000"  # completa lo que faltaba
    fuentes = {f["fuente"] for f in conn.execute("SELECT fuente FROM origenes WHERE persona_id = ?", (queda,))}
    assert fuentes == {"Bombo · Evento Ejemplo", "Lista Ejemplo"}
    union = conn.execute("SELECT * FROM uniones").fetchone()
    assert (union["queda_id"], union["se_va_id"], union["se_va_email"]) == (queda, se_va, "ana.otra@example.com")


def test_el_mail_de_la_ficha_que_se_fue_ya_no_crea_otra_persona(conn, tmp_path):
    queda, se_va = dos_fichas_de_ana(conn, tmp_path)
    unir(conn, queda, se_va)
    persona_id, nueva = guardar(conn, email="ana.otra@example.com", nombre="Ana Ejemplo")
    assert (persona_id, nueva) == (queda, False)


def test_una_baja_del_otro_mail_saca_a_la_persona(conn, tmp_path):
    queda, se_va = dos_fichas_de_ana(conn, tmp_path)
    unir(conn, queda, se_va)
    dar_de_baja(conn, "ana.otra@example.com")
    assert "ana.ejemplo@example.com" not in mails(segmento(conn))


def test_unir_mueve_las_entradas(conn, tmp_path):
    importar_bombo(conn, bombo(tmp_path), "Evento Ejemplo", "2026-05-16")
    ids = {f["email"]: f["id"] for f in conn.execute("SELECT id, email FROM personas")}
    unir(conn, ids["ana.ejemplo@example.com"], ids["diego.ficticio@example.com"])
    compradas = conn.execute(
        "SELECT COUNT(*) FROM entradas WHERE comprador_id = ?", (ids["ana.ejemplo@example.com"],)
    ).fetchone()[0]
    assert compradas == 4


def test_unir_no_acepta_la_misma_ficha_ni_una_que_no_existe(conn, tmp_path):
    queda, _ = dos_fichas_de_ana(conn, tmp_path)
    with pytest.raises(ValueError):
        unir(conn, queda, queda)
    with pytest.raises(LookupError):
        unir(conn, queda, 999)
    assert contar(conn, "uniones") == 0
