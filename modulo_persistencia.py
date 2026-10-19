""" 
Modulo de persistencia de datos.
Guarda y carga empleados y asistencias en archivos de texto (csv),
que sirven como almacenamiento permanente entre ejecuciones  del programa.
Usa  manejo de exepciones para no cerrar el programa si el archivo esta
bloqueado, no se puede escribir o tiene un formato dañado.
"""

import csv
import os

CARPETA_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ARCHIVO_EMPLEADOS = os.path.join(CARPETA_DATA, "empleados.csv")
ARCHIVO_ASISTENCIAS = os.path.join(CARPETA_DATA, "asistencia.csv")

CAMPOS_EMPELADOS = ["CODIGO", "NOMBRES", "apellidos", "dni", "cargo", "turno", "tarifa_hora", "estado"]
CAMPOS_ASISTENCIA =[
    "codigo_empleados", 
    "fecha",
    "turno",
    "hora_entrada",
    "hora_salida",
    "hora_trabajadas",
    "tardanzas",
    "observaciones",

]

def _escribir_csv(ruta, campos, filas):
    """Escribe una lista de diccionarios en un csv. Retorna true si tuvo exito."""
    try:
        if os.path.dirname(ruta) == CARPETA_DATA:
            os.makedirs(CARPETA_DATA, exist_ok=true)
        with open(ruta, mode="W", newline="", encoding="utf-8") as archivo:
             escritor = csv.DictWrite(archivo, fieldnames=campos, extrasaction="ignore")
             escritor.writeheader()
        for fila in filas:
             escritor.writerow(fila)
        return True
    except OSError as error:
        print (f"[ERROR] no se pudo cargar'{ruta}': {error}")
        return False

def _leer_csv(ruta, campos):
    """
    Lee un csv como lista de diccionario. Si no existe, retorna lista vacia.
    Si el archivo viene de una version anterior y le faltan columnas, se
    completan con  texto vacio para que el resto del programa no falle.
    """
    if not os.path.exists(ruta):
        return[]
        try:
            with open (ruta, mode="r", newline="", encoding="utf-8") as archivo:
                filas = [fila for fila in csv.DictReader(archivo)]
        except (OSError, csv.Error, UnicodeDecodeError) as error:
            print(f"[ADVERTENCIA] no se pudo leer '{ruta}' ({error}).")
            print("             se inicia en una lista vacia.")
            return []
        for fila in filas :
            for campo in campos:
                if fila.get(campo) is None:
                    fila[campo] = ""
        return filas
    
    def cargar_empleados(ruta=ARCHIVO_EMPLEADOS):
        return _leer_csv(rutas,CAMPOS_EMPELADOS)

    def guardar_asistencias(lista_asistencia, ruta=ARCHIVO_ASISTENCIAS):
        return _escribir_csv(ruta, CAMPOS_ASISTENCIA, lista_asistencia)

    def cargar_asistencias(ruta=ARCHIVO_ASISTENCIAS):
        return _leer_csv(ruta, CAMPOS_ASISTENCIAS)