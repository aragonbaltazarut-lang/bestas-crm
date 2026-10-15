"""Línea de comandos:

python -m crm bombo <xlsx> --evento "The Bow" --fecha 2026-05-16
python -m crm lista <xlsx> --fuente "Base de contactos"
python -m crm reporte
python -m crm enriquecer
python -m crm exportar <csv> [--fuente ...] [--genero mujer|hombre] [--compraron | --no-compraron] [--fechas N]
python -m crm baja <mail> [--motivo ...]
python -m crm unir <id que queda> <id que se va>
"""

import argparse
import sys

from .bajas import dar_de_baja
from .db import conectar
from .enriquecer import recalcular
from .exportar import a_csv, segmento
from .importar import importar_bombo, importar_lista
from .personas import unir
from .reportes import REPORTES, tabla


def main():
    parser = argparse.ArgumentParser(prog="crm")
    parser.add_argument("--db", default="crm.db", help="archivo SQLite (crm.db)")
    sub = parser.add_subparsers(dest="comando", required=True)

    bombo = sub.add_parser("bombo", help="cargar el export de entradas de Bombo de un evento")
    bombo.add_argument("xlsx")
    bombo.add_argument("--evento", required=True)
    bombo.add_argument("--fecha", required=True, help="AAAA-MM-DD")

    lista = sub.add_parser("lista", help="cargar una planilla suelta de nombres y mails")
    lista.add_argument("xlsx")
    lista.add_argument("--fuente", required=True, help="cómo se llama esta base")

    sub.add_parser("reporte", help="mostrar los reportes")
    sub.add_parser("enriquecer", help="volver a estimar género y tipo de toda la base")

    exportar = sub.add_parser("exportar", help="sacar un segmento a CSV (sin las bajas)")
    exportar.add_argument("csv")
    exportar.add_argument("--fuente")
    exportar.add_argument("--genero", choices=["mujer", "hombre"])
    exportar.add_argument("--compraron", dest="compro", action="store_true", default=None)
    exportar.add_argument("--no-compraron", dest="compro", action="store_false")
    exportar.add_argument("--fechas", type=int, help="que hayan ido a esta cantidad de fechas o más")

    baja = sub.add_parser("baja", help="dar de baja un mail: no vuelve a salir en un envío")
    baja.add_argument("mail")
    baja.add_argument("--motivo")

    unir_ = sub.add_parser("unir", help="unir dos fichas que son la misma persona")
    unir_.add_argument("queda", type=int, help="id de la ficha que queda")
    unir_.add_argument("se_va", type=int, help="id de la ficha que se une a la otra y se borra")

    args = parser.parse_args()
    conn = conectar(args.db)
    try:
        if args.comando == "bombo":
            resumen = importar_bombo(conn, args.xlsx, args.evento, args.fecha)
        elif args.comando == "lista":
            resumen = importar_lista(conn, args.xlsx, args.fuente)
        elif args.comando == "enriquecer":
            resumen = recalcular(conn)
        elif args.comando == "exportar":
            total = a_csv(segmento(conn, args.fuente, args.genero, args.compro, args.fechas), args.csv)
            print(f"{total} personas en {args.csv}")
            return
        elif args.comando == "baja":
            nueva = dar_de_baja(conn, args.mail, args.motivo)
            print("Baja registrada" if nueva else "Ese mail ya estaba dado de baja")
            return
        elif args.comando == "unir":
            union = unir(conn, args.queda, args.se_va)
            print(f"{union['se_va']} ({args.se_va}) quedó unida a {union['queda']} ({args.queda})")
            return
        else:
            for titulo, sql in REPORTES.items():
                print(f"\n{titulo}\n")
                print(tabla(conn, sql))
            return
    except (ValueError, LookupError) as error:
        sys.exit(f"Error: {error}")
    finally:
        conn.close()
    print(", ".join(f"{n} {k}" for k, n in resumen.items()))


if __name__ == "__main__":
    main()
