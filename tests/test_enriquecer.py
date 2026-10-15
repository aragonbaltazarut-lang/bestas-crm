from crm.enriquecer import es_organizacion, estimar_genero, nombre_de_pila


def test_nombre_de_pila_sin_tildes():
    assert nombre_de_pila("María José Ejemplo") == "maria"
    assert nombre_de_pila("ana@example.com") is None


def test_estima_nombres_y_apodos_de_aca():
    assert estimar_genero("Nicolás Ejemplo") == estimar_genero("Nicolas Ejemplo") == "hombre"
    assert estimar_genero("Cami Ejemplo") == "mujer"
    assert estimar_genero("Fede Ejemplo") == "hombre"


def test_la_tilde_cambia_el_genero():
    assert estimar_genero("José Ejemplo") == "hombre"
    assert estimar_genero("Jose Ejemplo") is None  # acá suele ser Josefina


def test_no_adivina_lo_ambiguo_ni_lo_desconocido():
    assert estimar_genero("Juli Ejemplo") is None   # Julieta o Julián
    assert estimar_genero("Manu Ejemplo") is None   # Manuel o Manuela
    assert estimar_genero("Zxqw Ejemplo") is None


def test_organizaciones():
    assert es_organizacion("Fiestas Ejemplo", "a@example.com")
    assert es_organizacion(None, "prensa@example.com")
    assert not es_organizacion("Ana Ejemplo", "hola@anaejemplo.com")  # una persona con su dominio
    assert es_organizacion("ejemplo.com.ar", None)
    assert not es_organizacion("Ana Ejemplo", "ana@example.com")
