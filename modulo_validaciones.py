"""
Modulo de validaciones.
Centraliza todas las reglas de validacion de datos de entrada
(codigos, DNI, horas, fechas, cargos, turnos).
"""

import re
from datetime import datetime

CARGOS_VALIDOS = ["Parrillero", "Mesero", "Caja", "Cocina", "Administracion"]
TURNOS_VALIDOS = ["Mañana", "Tarde"]  # SG Aron's EIRL trabaja con 2 turnos 


def validar_codigo_formato(codigo):
    """Codigo debe tener formato E### (ej: E001)."""
    patron = r"^E\d{3}$"
    return bool(re.match(patron, codigo.strip().upper()))


def validar_dni(dni):
    """DNI debe tener exactamente 8 digitos numericos."""
    return dni.strip().isdigit() and len(dni.strip()) == 8


def validar_texto_no_vacio(texto):
    """Valida que un texto (nombres, apellidos) no este vacio."""
    return len(texto.strip()) > 0


def validar_cargo(cargo):
    return cargo.strip().title() in CARGOS_VALIDOS


def normalizar_turno(turno):
    """
    Convierte lo que escribe el usuario al nombre oficial del turno.
    Acepta 'M'/'T' o el nombre completo, con o sin tilde.
    Retorna 'Mañana', 'Tarde' o None si no es valido.
    """
    t = turno.strip().lower().replace("ñ", "n")
    if t in ("m", "manana"):
        return "Mañana"
    if t in ("t", "tarde"):
        return "Tarde"
    return None


def validar_turno(turno):
    """El turno es valido si se puede normalizar a Mañana o Tarde."""
    return normalizar_turno(turno) is not None


def validar_tarifa_hora(tarifa_str):
    """La tarifa por hora debe ser un numero positivo (soles)."""
    try:
        tarifa = float(tarifa_str)
        return tarifa > 0
    except (ValueError, TypeError):
        return False


def validar_formato_fecha(fecha_str):
    """Formato esperado: dd/mm/yyyy (ej: 31/12/2023)."""
    try:
        datetime.strptime(fecha_str.strip(), "%d/%m/%Y")
        return True
    except ValueError:
        return False


def validar_formato_mes(fecha_str):
    """Formato esperado para planilla: mm/yyyy (ej: 12/2023)."""
    try:
        datetime.strptime(fecha_str.strip(), "%m/%Y")
        return True
    except ValueError:
        return False

    
def normalizar_hora(hora_str):
    """
    Devuelve la hora siempre como HH:MM con cero inicial (´8:05` -> `08:05`).
    o None si el formato no es valido. es necesario porque las horas se
    comparan como texto y ´8:05` > ´14:00`daria un resultado incorrecto.
    """ 
    try:
        return datetime.strptime(hora_str.strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def vaidar_formato_hora(hora_str):
    """Formato esperado: HH:MM en 24 horas."""
    try:
        datetime.strptime(hora_str.strip(), "%H:%M")
        return True
    except ValueError:
        return False


def hora_es_posterior(hora_entrada, hora_salida):
    """verifica que la hora de salida sea posterior a la hora de entrada."""
    fmt = "%H:%M"
    return datetime.strptime(hora_salida, fmt) > datetime.strptime(hora_entrada, fmt)


def codigo_existe(codigo, lista_empleados):
    """Busqueda lineal: retorna True si el codigo ya esta registrado."""
    for empleado in lista_empleados:
        if empleado ["codigo"] == codigo.strip().upper():
            return True
    return False