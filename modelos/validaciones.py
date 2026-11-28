# -*- coding: utf-8 -*-
"""
MODELO - Validaciones (logica de negocio).
Centraliza todas las reglas de validacion de datos de entrada
(codigos, DNI, horas, fechas, cargos, turnos). No depende de vistas ni controladores.
"""

import re
from datetime import datetime

CARGOS_VALIDOS = ["Parrillero", "Mesero", "Caja", "Cocina", "Administracion"]
TURNOS_VALIDOS = ["Mañana", "Tarde"]  # SG Aron's EIRL trabaja con 2 turnos


def validar_codigo_formato(codigo):
    """Codigo debe tener formato E### (ej: E001)."""
    return re.fullmatch(r"E[0-9]{3}", codigo.strip().upper()) is not None


def validar_dni(dni_str):
    """
    DNI peruano: exactamente 8 digitos (0-9). Ademas se rechazan los numeros que
    no pueden ser reales o son claramente inventados:
      - todos los digitos iguales: 00000000, 11111111, 99999999...
      - secuencias consecutivas: 12345678, 87654321, 01234567...
      - patrones repetidos: 12121212, 12341234...
    """
    dni = dni_str.strip()
    if re.fullmatch(r"[0-9]{8}", dni) is None:
        return False
    if len(set(dni)) == 1:                                   # 00000000, 11111111...
        return False
    pasos = {(int(b) - int(a)) % 10 for a, b in zip(dni, dni[1:])}
    if pasos == {1} or pasos == {9}:                         # ascendente o descendente
        return False
    for tamano in (2, 4):                                    # bloque que se repite
        if dni == dni[:tamano] * (8 // tamano):
            return False
    return True


def validar_nombre(texto):
    """
    Nombres y apellidos: solo letras de cualquier idioma (tildes, ñ, ü, ç...)
    separadas por espacio, guion o apostrofe. Rechaza numeros, vacios y
    simbolos como @. Se trabaja con texto Unicode (UTF-8).
    """
    letras = r"[^\W\d_]+"  # \w sin digitos ni guion bajo = solo letras Unicode
    return re.fullmatch(letras + "([ '’-]" + letras + ")*", texto.strip()) is not None


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


# Limite de seguridad de la tarifa (soles por hora). Evita valores absurdos como
# infinito, 1e999 o 999999999. Valor de ejemplo: confirmar con la gerencia.
MAX_TARIFA_HORA = 500


def validar_tarifa_hora(tarifa_str):
    """
    Tarifa por hora en soles: numero con punto decimal y hasta 2 decimales,
    mayor que 0 y no mayor que MAX_TARIFA_HORA.
    Rechaza 'inf', 'infinity', 'nan', '1e999', notacion cientifica, signos,
    comas y digitos que no sean 0-9.
    """
    texto = str(tarifa_str).strip()
    if re.fullmatch(r"[0-9]+(\.[0-9]{1,2})?", texto) is None:
        return False
    return 0 < float(texto) <= MAX_TARIFA_HORA


def validar_formato_fecha(fecha_str):
    """Formato estricto AAAA-MM-DD (con ceros) y fecha real."""
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", fecha_str.strip()) is None:
        return False
    try:
        datetime.strptime(fecha_str.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validar_formato_mes(mes_str):
    """Formato estricto para la planilla: AAAA-MM (ej: 2026-09)."""
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}", mes_str.strip()) is None:
        return False
    try:
        datetime.strptime(mes_str.strip(), "%Y-%m")
        return True
    except ValueError:
        return False


_HORA_12 = re.compile(r"(\d{1,2}):(\d{2})\s*([AaPp])\.?\s*[Mm]\.?")


def normalizar_hora(hora_str):
    """
    Devuelve la hora siempre como HH:MM en 24 horas con cero inicial ('8:05' -> '08:05'),
    o None si el formato no es valido. Es necesario porque las horas se comparan como
    texto y '8:05' > '14:00' daria un resultado incorrecto.
    Acepta HH:MM (24 h) y tambien h:MM AM / h:MM PM (12 h, con o sin espacio, 'am', 'p. m.'):
    '8:05 PM' -> '20:05', '12:30 AM' -> '00:30', '12:00 PM' -> '12:00'.
    Internamente todo se guarda en 24 h; el AM/PM es solo la forma de escribirla y mostrarla.
    """
    texto = str(hora_str).strip()
    coincide = _HORA_12.fullmatch(texto)
    if coincide:
        hora, minuto, periodo = int(coincide.group(1)), int(coincide.group(2)), coincide.group(3).upper()
        if not (1 <= hora <= 12 and 0 <= minuto <= 59):
            return None
        if periodo == "A":
            hora = 0 if hora == 12 else hora
        else:
            hora = 12 if hora == 12 else hora + 12
        return f"{hora:02d}:{minuto:02d}"
    try:
        return datetime.strptime(texto, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def formatear_hora_12(hora_str):
    """
    Muestra una hora guardada en 24 h como se ve en la interfaz: '08:05' -> '08:05 AM',
    '14:30' -> '02:30 PM', '00:15' -> '12:15 AM'. Un texto vacio o invalido se devuelve igual.
    """
    normal = normalizar_hora(hora_str) if str(hora_str).strip() else None
    if normal is None:
        return str(hora_str)
    hora, minuto = int(normal[:2]), normal[3:]
    periodo = "AM" if hora < 12 else "PM"
    return f"{(hora % 12) or 12:02d}:{minuto} {periodo}"


def validar_formato_hora(hora_str):
    """Formato esperado: HH:MM en 24 horas o h:MM AM/PM."""
    return normalizar_hora(hora_str) is not None


def hora_es_posterior(hora_entrada, hora_salida):
    """Verifica que la hora de salida sea posterior a la de entrada."""
    fmt = "%H:%M"
    return datetime.strptime(hora_salida, fmt) > datetime.strptime(hora_entrada, fmt)


def codigo_existe(codigo, lista_empleados):
    """Busqueda lineal: retorna True si el codigo ya esta registrado."""
    for empleado in lista_empleados:
        if empleado["codigo"] == codigo.strip().upper():
            return True
    return False
