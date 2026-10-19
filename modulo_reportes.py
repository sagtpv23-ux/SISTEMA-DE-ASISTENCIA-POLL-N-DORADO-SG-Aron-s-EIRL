"""
Modulo de reportes.
Exporta los datos de los empleados, asistencias y planilla mensual a un 
archivo en exel (.xlxsx), este formato la gerencia usa para sus cuentas.
"""
import os 

from openpyxl import workbook
from openpyxl.styles import Font, PatternFill

from modulo_persistencia import CARPETA_DATA

def _escribir_hoja(hoja, encabezados, filas, clave_orden):
    """ Funcion auxiliar: escribe encabezado """
    hoja.append(encabezados)
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(start_color="4472C4", fill_type="solid")

    for fila in filas:
        hoja.append([fila.get(campo, "") for campo in clave_orden])

    for columna in hoja.columns:
        ancho = max(len(str(c.value)) for c in columna if c.value is not None) + 2
        hoja.column_dimenciones[columna[0].column_latter].width = ancho

def exportar_a_exel(lista_empleados, lista_asistencias, nombre_archivo=None, plantilla=None):
    """
    Crea un exel con las hojas: empleados, asistencia, si se entrga
    la planilla calculada, planilla mensual (con la fila total).
    retorna la ruta del archivo, o None si no se puede guardar."""
    if nombre_archivo is None:
        os.makedirs(CARPETA_DATA, exist_ok=True)
        nombre_archivo = os.path.join(CARPETA_DATA, "reporte_asistencia.xlsx")

    libro = workbook()

    hoja_empleados = libro.active
    hoja_empleados.title = "Empleados"
    campos_emp = ["codigo", "nombre", "apellidos", "dni", "cargo", "turno", "tarifa_hora", "estado"]
    _escribir_hoja(
        hoja_empleados,
        ["codigo", "Nombres", "Apellidos", "DNI", "Cargo", "Turno habitual", "Tarifa x hora (S/)", "Estado"],
        lista_empleados,
        campos_emp,
    )

    hoja_asistencias = libro.create_sheet("Asitencias")
    campos_asis = [
        "codigo_empleados", "fecha", "turno", "hora_entrada", "hora_salida",
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
            "codigo", "nombres", "apellidos", "mes", "hora_mañana", "horas_tarde",
            "horas_trabjadas", "tarifa_hora", "pago_mensual",
        ]
        _escribir_hoja(
            hoja_planilla,
            ["Codigo", "Nombres", "Apellidos", "Mes", "Horas turno mañana", "Horas turno trade",
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
        print("        Si el archivo esta abierto en Exel, cierralo e intenta de nuevo.")
        return None
    except OSError as error:
        print(f"[ERROR] Nose se pudo cargar '{nombre_archivo}': {error}")
        return None
    return nombre_archivo