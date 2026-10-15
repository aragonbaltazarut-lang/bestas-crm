import sqlite3

from crm.db import MIGRACIONES, V1, conectar


def version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def test_una_base_nueva_queda_en_la_ultima_version(tmp_path):
    conn = conectar(tmp_path / "nueva.db")
    assert version(conn) == len(MIGRACIONES)
    conn.close()


def test_conectar_dos_veces_no_repite_migraciones(tmp_path):
    conectar(tmp_path / "base.db").close()
    conn = conectar(tmp_path / "base.db")  # si volviera a correr la 2, el ALTER TABLE fallaría
    assert version(conn) == len(MIGRACIONES)
    conn.close()


def test_una_base_vieja_se_actualiza_sin_perder_datos(tmp_path):
    # Una base armada antes de las migraciones: tiene las tablas de la versión 1 y user_version 0.
    ruta = tmp_path / "vieja.db"
    vieja = sqlite3.connect(ruta)
    vieja.executescript(V1)
    vieja.execute(
        "INSERT INTO personas (email, email_clave, nombre, creada, actualizada) "
        "VALUES ('ana@example.com', 'ana@example.com', 'Ana Ejemplo', 'hoy', 'hoy')"
    )
    vieja.commit()
    vieja.close()

    conn = conectar(ruta)
    assert version(conn) == len(MIGRACIONES)
    assert conn.execute("SELECT nombre FROM personas").fetchone()["nombre"] == "Ana Ejemplo"
    columnas = {c["name"] for c in conn.execute("PRAGMA table_info(entradas)")}
    assert "vendedor" in columnas
    conn.close()
