# -*- coding: utf-8 -*-
"""
VISTA - Reporte en CSV (archivo de texto).
Genera tres archivos: empleados.csv, asistencias.csv y planilla_AAAA-MM.csv.
Codificacion UTF-8 con BOM (utf-8-sig) para que Excel muestre bien tildes y ñ.
"""

import csv
import os

from models.base_datos import CARPETA_DATA, CAMPOS_ASISTENCIAS, CAMPOS_EMPLEADOS

CAMPOS_PLANILLA = [
    "codigo", "nombres", "apellidos", "mes", "horas_manana", "horas_tarde",
    "horas_trabajadas", "tarifa_hora", "pago_mensual",
]


def _escribir(ruta, campos, filas):
    with open(ruta, mode="w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


def exportar_a_csv(lista_empleados, lista_asistencias, planilla=None, carpeta=None, mes=""):
    """
    Escribe los CSV en 'carpeta' (por defecto data/). Retorna la lista de rutas
    generadas, o None si no se pudo guardar (por ejemplo, archivo abierto en Excel).
    """
    if carpeta is None:
        carpeta = CARPETA_DATA
    try:
        os.makedirs(carpeta, exist_ok=True)
        rutas = []
        for nombre, campos, filas in (
            ("empleados.csv", CAMPOS_EMPLEADOS, lista_empleados),
            ("asistencias.csv", CAMPOS_ASISTENCIAS, lista_asistencias),
        ):
            ruta = os.path.join(carpeta, nombre)
            _escribir(ruta, campos, filas)
            rutas.append(ruta)
        if planilla is not None:
            ruta = os.path.join(carpeta, f"planilla_{mes or 'mensual'}.csv")
            _escribir(ruta, CAMPOS_PLANILLA, planilla)
            rutas.append(ruta)
        return rutas
    except (PermissionError, OSError) as error:
        print(f"[ERROR] No se pudo guardar el CSV en '{carpeta}': {error}")
        print("        Si el archivo esta abierto en Excel, cierrelo e intente de nuevo.")
        return None
