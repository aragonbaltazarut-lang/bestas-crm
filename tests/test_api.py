import pytest
from fastapi.testclient import TestClient

from crm.api import app, get_conn
from crm.db import conectar
from crm.importar import importar_bombo, importar_lista
from scripts.generar_ejemplos import bombo, lista


@pytest.fixture
def cliente(tmp_path):
    conn = conectar(tmp_path / "test.db")
    importar_bombo(conn, bombo(tmp_path), "Evento Ejemplo", "2026-05-16")
    importar_lista(conn, lista(tmp_path), "Lista Ejemplo")
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def test_buscar_por_nombre(cliente):
    nombres = [p["nombre"] for p in cliente.get("/personas", params={"buscar": "prueba"}).json()["personas"]]
    assert nombres == ["Bruno Prueba", "Florencia Prueba"]


def test_buscar_por_fuente(cliente):
    respuesta = cliente.get("/personas", params={"fuente": "Bombo · Evento Ejemplo"}).json()
    assert respuesta["total"] == len(respuesta["personas"]) == 5


def test_pagina_de_a_partes(cliente):
    pagina = cliente.get("/personas", params={"limite": 2, "desde": 2}).json()
    assert pagina["total"] == 7
    assert len(pagina["personas"]) == 2


def test_filtra_por_genero(cliente):
    mujeres = cliente.get("/personas", params={"genero": "mujer"}).json()["personas"]
    assert all(p["genero"] == "mujer" for p in mujeres) and mujeres


def test_ficha_con_origenes_y_entradas(cliente):
    ana = cliente.get("/personas", params={"buscar": "ana.ejemplo"}).json()["personas"][0]
    ficha = cliente.get(f"/personas/{ana['id']}").json()
    assert {o["fuente"] for o in ficha["origenes"]} == {"Bombo · Evento Ejemplo", "Lista Ejemplo"}
    assert len(ficha["entradas"]) == 2
    assert [e["asistio"] for e in ficha["entradas"]] == [True, False]


def test_persona_inexistente(cliente):
    assert cliente.get("/personas/999").status_code == 404


def test_resolver_una_incidencia(cliente):
    abiertas = cliente.get("/incidencias").json()
    assert len(abiertas) == 3
    assert cliente.post(f"/incidencias/{abiertas[0]['id']}/resolver").status_code == 200
    assert len(cliente.get("/incidencias").json()) == 2


def test_reportes(cliente):
    reportes = cliente.get("/reportes").json()
    cruzadas = {p["email"] for p in reportes["Personas en más de una fuente"]}
    assert cruzadas == {"ana.ejemplo@example.com", "bruno.prueba@example.com", "lucia.demo@example.com"}


def test_ficha_con_historial_y_si_recibe_mails(cliente):
    ana = cliente.get("/personas", params={"buscar": "ana.ejemplo"}).json()["personas"][0]
    ficha = cliente.get(f"/personas/{ana['id']}").json()
    assert ficha["historial"]["fechas"] == 1
    assert ficha["historial"]["entradas_compradas"] == 2
    assert ficha["recibe_mails"] is True


def test_una_baja_por_la_api(cliente):
    respuesta = cliente.post("/bajas", json={"email": "ana.ejemplo@example.com", "motivo": "lo pidió"})
    assert respuesta.json()["nueva"] is True
    assert [b["email"] for b in cliente.get("/bajas").json()] == ["ana.ejemplo@example.com"]
    ana = cliente.get("/personas", params={"buscar": "ana.ejemplo"}).json()["personas"][0]
    assert cliente.get(f"/personas/{ana['id']}").json()["recibe_mails"] is False
    assert cliente.post("/bajas", json={"email": "sin arroba"}).status_code == 422


def test_unir_por_la_api(cliente):
    personas = {p["email"]: p["id"] for p in cliente.get("/personas").json()["personas"]}
    queda, se_va = personas["ana.ejemplo@example.com"], personas["lucia.demo@example.com"]
    assert cliente.post(f"/personas/{queda}/unir", json={"se_va": se_va}).status_code == 200
    assert cliente.get(f"/personas/{se_va}").status_code == 404
    assert cliente.get(f"/personas/{queda}").json()["otros_mails"] == ["lucia.demo@example.com"]
    assert cliente.post(f"/personas/{queda}/unir", json={"se_va": queda}).status_code == 400
    assert cliente.post(f"/personas/{queda}/unir", json={"se_va": 999}).status_code == 404


def test_con_token_hay_que_mandarlo(cliente, monkeypatch):
    monkeypatch.setenv("CRM_TOKEN", "secreto")
    assert cliente.get("/personas").status_code == 401
    assert cliente.get("/personas", headers={"Authorization": "Bearer otro"}).status_code == 401
    assert cliente.get("/personas", headers={"Authorization": "Bearer secreto"}).status_code == 200
