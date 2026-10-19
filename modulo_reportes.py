"""
Modulo de reportes.
Exporta los datos de empleados, asistencias y planilla mensual a un
archivo Excel (.xlsx), formato que la gerencia ya utiliza para sus cuentas.
"""

import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from modulo_persistencia import CARPETA_DATA


def _escribir_hoja(hoja, encabezados, filas, clave_orden):
    """Funcion auxiliar: escribe encabezados con estilo y las filas de datos."""
    hoja.append(encabezados)
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(start_color="4472C4", fill_type="solid")

    for fila in filas:
        hoja.append([fila.get(campo, "") for campo in clave_orden])

    for columna in hoja.columns:
        ancho = max(len(str(c.value)) for c in columna if c.value is not None) + 2
        hoja.column_dimensions[columna[0].column_letter].width = ancho


def exportar_a_excel(lista_empleados, lista_asistencias, nombre_archivo=None, planilla=None):
    """
    Genera un Excel con las hojas: Empleados, Asistencias y, si se entrega
    la planilla calculada, Planilla mensual (con fila de total).
    Retorna la ruta del archivo, o None si no se pudo guardar.
    """
    if nombre_archivo is None:  # por defecto: data/reporte_asistencia.xlsx
        os.makedirs(CARPETA_DATA, exist_ok=True)
        nombre_archivo = os.path.join(CARPETA_DATA, "reporte_asistencia.xlsx")

    libro = Workbook()

    hoja_empleados = libro.active
    hoja_empleados.title = "Empleados"
    campos_emp = ["codigo", "nombres", "apellidos", "dni", "cargo", "turno", "tarifa_hora", "estado"]
    _escribir_hoja(
        hoja_empleados,
        ["Codigo", "Nombres", "Apellidos", "DNI", "Cargo", "Turno habitual", "Tarifa x hora (S/)", "Estado"],
        lista_empleados,
        campos_emp,
    )

    hoja_asistencias = libro.create_sheet("Asistencias")
    campos_asis = [
        "codigo_empleado", "fecha", "turno", "hora_entrada", "hora_salida",
        "horas_trabajadas", "tardanza", "observaciones",
    ]
    _escribir_hoja(
        hoja_asistencias,
        ["Codigo", "Fecha", "Turno", "Hora entrada", "Hora salida", "Horas trabajadas", "Tardanza", "Observaciones"],
        lista_asistencias,
        campos_asis,
    )

    if planilla is not None:
        hoja_planilla = libro.create_sheet("Planilla mensual")
        campos_planilla = [
            "codigo", "nombres", "apellidos", "mes", "horas_manana", "horas_tarde",
            "horas_trabajadas", "tarifa_hora", "pago_mensual",
        ]
        _escribir_hoja(
            hoja_planilla,
            ["Codigo", "Nombres", "Apellidos", "Mes", "Horas turno Mañana", "Horas turno Tarde",
             "Horas totales", "Tarifa x hora (S/)", "Pago mensual (S/)"],
            planilla,
            campos_planilla,
        )
        total = round(sum(r["pago_mensual"] for r in planilla), 2)
        hoja_planilla.append(["", "TOTAL A PAGAR", "", "", "", "", "", "", total])
        for celda in hoja_planilla[hoja_planilla.max_row]:
            celda.font = Font(bold=True)

    try:
        libro.save(nombre_archivo)
    except PermissionError:
        print(f"[ERROR] No se pudo guardar '{nombre_archivo}'.")
        print("        Si el archivo esta abierto en Excel, cierrelo e intente de nuevo.")
        return None
    except OSError as error:
        print(f"[ERROR] No se pudo guardar '{nombre_archivo}': {error}")
        return None
    return nombre_archivo