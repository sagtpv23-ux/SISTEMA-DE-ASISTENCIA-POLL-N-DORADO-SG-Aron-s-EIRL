"""
VISTA - Reporte en JSON (archivo de texto).
Un solo archivo con tres secciones: empleados, asistencias y planilla.
UTF-8 real (ensure_ascii=False): las tildes y la ñ se ven tal cual.
"""

import json
import os
from datetime import datetime

from models.base_datos import CARPETA_DATA


def exportar_a_json(lista_empleados, lista_asistencias, planilla=None, nombre_archivo=None, mes=""):
    """
    Genera data/reporte_asistencia.json (o la ruta indicada).
    Retorna la ruta, o None si no se pudo guardar.
    """
    if nombre_archivo is None:
        os.makedirs(CARPETA_DATA, exist_ok=True)
        nombre_archivo = os.path.join(CARPETA_DATA, "reporte_asistencia.json")
    contenido = {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mes_planilla": mes,
        "empleados": lista_empleados,
        "asistencias": lista_asistencias,
        "planilla": planilla if planilla is not None else [],
    }
    try:
        with open(nombre_archivo, mode="w", encoding="utf-8") as archivo:
            json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        return nombre_archivo
    except (PermissionError, OSError, TypeError) as error:
        print(f"[ERROR] No se pudo guardar '{nombre_archivo}': {error}")
        return None
