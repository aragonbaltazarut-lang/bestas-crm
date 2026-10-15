import pytest

from crm.db import conectar
from crm.exportar import segmento
from crm.importar import importar_bombo
from crm.reportes import PUBLICO_QUE_VOLVIO, VENTAS_POR_VENDEDOR
from scripts.generar_ejemplos import bombo, bombo_segunda


@pytest.fixture
def conn(tmp_path):
    conexion = conectar(tmp_path / "test.db")
    importar_bombo(conexion, bombo(tmp_path), "Evento Ejemplo", "2026-05-16")
    importar_bombo(conexion, bombo_segunda(tmp_path), "Evento Ejemplo 2", "2026-08-22")
    yield conexion
    conexion.close()


def historial(conn, email):
    return conn.execute(
        "SELECT h.* FROM historial h JOIN personas p ON p.id = h.persona_id WHERE p.email = ?", (email,)
    ).fetchone()


def test_historial_de_quien_fue_a_las_dos(conn):
    ana = historial(conn, "ana.ejemplo@example.com")
    assert (ana["fechas"], ana["primera"], ana["ultima"]) == (2, "2026-05-16", "2026-08-22")
    assert (ana["entradas_compradas"], ana["gastado"]) == (3, 22900 * 2 + 27900)


def test_quien_fue_con_una_entrada_que_le_pasaron_tambien_cuenta(conn):
    bruno = historial(conn, "bruno.prueba@example.com")  # en la primera, la entrada se la pasó Ana
    assert (bruno["fechas"], bruno["entradas_compradas"]) == (2, 1)


def test_publico_que_volvio(conn):
    filas = conn.execute(PUBLICO_QUE_VOLVIO).fetchall()
    assert {f["email"] for f in filas} == {"ana.ejemplo@example.com", "bruno.prueba@example.com"}


def test_exportar_a_quien_fue_a_varias_fechas(conn):
    assert {f["email"] for f in segmento(conn, fechas=2)} == {
        "ana.ejemplo@example.com", "bruno.prueba@example.com",
    }


def test_ventas_por_vendedor(conn):
    filas = {(f["evento"], f["vendedor"]): (f["entradas"], f["compradores"])
             for f in conn.execute(VENTAS_POR_VENDEDOR)}
    assert filas[("Evento Ejemplo", "Rocío Vendedora")] == (2, 1)  # el combo de Diego
    assert filas[("Evento Ejemplo", "Bestas Productions")] == (4, 3)
    assert filas[("Evento Ejemplo 2", "Rocío Vendedora")] == (2, 2)
