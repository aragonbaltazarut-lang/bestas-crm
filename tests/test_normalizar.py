from crm import normalizar as n


def test_email_se_normaliza():
    assert n.email("  Carla.Inventada@Example.com ") == "carla.inventada@example.com"


def test_email_sin_dominio_no_es_email():
    assert n.email("martina.muestra@example") is None
    assert n.email("sin arroba") is None


def test_no_corrige_el_mismo_proveedor_en_otro_pais():
    assert n.email_corregido("a@yahoo.com.br") == ("a@yahoo.com.br", False)
    assert n.email_corregido("a@hotmail.com.uy") == ("a@hotmail.com.uy", False)
    assert n.email_corregido("a@email.com") == ("a@email.com", False)
    assert n.email_corregido("a@gmail.com.br") == ("a@gmail.com", True)  # Gmail no tiene dominios por país


def test_nombre_arregla_mayusculas_y_respeta_lo_que_ya_estaba_bien():
    assert n.nombre("lulii", "ejemplo prueba") == "Lulii Ejemplo Prueba"
    assert n.nombre("JUAN DE LA PRUEBA") == "Juan de la Prueba"
    assert n.nombre("Ana DeMuestra") == "Ana DeMuestra"


def test_nombre_saca_la_puntuacion_de_una_lista_copiada():
    assert n.nombre("Lucía Demo:") == "Lucía Demo"


def test_dni_que_excel_guardo_como_numero():
    assert n.dni(40123456.0) == "40123456"
    assert n.dni("40.111.222") == "40111222"
    assert n.dni("123") is None


def test_genero_en_ingles_y_en_castellano():
    assert n.genero("Female") == n.genero("Mujer") == "mujer"
    assert n.genero("Male") == "hombre"
    assert n.genero("Otro") is None


def test_separa_las_notas_del_nombre():
    assert n.separar_nota("Ana Ejemplo (BOMBO) 👑") == ("Ana Ejemplo", "BOMBO")
    assert n.separar_nota("Juan Prueba PR | AGENCIA ™") == ("Juan Prueba PR", "AGENCIA")
    assert n.separar_nota("Luz Demo (sin cerrar") == ("Luz Demo", "sin cerrar")
    assert n.separar_nota("Juan D´Ejemplo") == ("Juan D'Ejemplo", None)
    assert n.separar_nota("Mica Ejemplo Rrpp CLUB - BAR") == ("Mica Ejemplo", "RRPP CLUB - BAR")


def test_dos_mails_en_una_celda():
    assert n.mails("a@example.com // b@example.com") == ["a@example.com", "b@example.com"]
    assert n.mails("-") == []


def test_detecta_caracteres_rotos():
    assert n.esta_roto("Sofía Pe\ufffda")
    assert not n.esta_roto("Sofía Peña")
