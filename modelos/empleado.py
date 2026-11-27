# -*- coding: utf-8 -*-
"""
MODELO - Empleados (logica de negocio).
Cubre: registro, modificacion, eliminacion (baja), listado, busqueda lineal,
busqueda binaria recursiva y ordenamiento por codigo (sorted de Python)
sobre la lista de empleados.
"""

from models.validaciones import (
    MAX_TARIFA_HORA,
    normalizar_turno,
    validar_codigo_formato,
    validar_dni,
    validar_nombre,
    validar_cargo,
    validar_turno,
    validar_tarifa_hora,
    codigo_existe,
)


def dni_existe(lista_empleados, dni):
    """Un DNI identifica a una sola persona: no puede repetirse entre trabajadores."""
    dni = dni.strip()
    return any(str(e["dni"]).strip() == dni for e in lista_empleados)


def registrar_empleado(lista_empleados, codigo, nombres, apellidos, dni, cargo, turno, tarifa_hora):
    """
    Registra un nuevo empleado tras validar todos sus datos.
    turno: turno habitual (M/Mañana o T/Tarde). Cada jornada puede registrarse
    con otro turno si el trabajador cubre un cambio (ver models/asistencia.py).
    tarifa_hora: pago por hora trabajada en soles, usado para calcular
    la planilla mensual (models/planilla.py).
    Retorna (True, mensaje) o (False, mensaje_error).
    """
    codigo = codigo.strip().upper()

    if not validar_codigo_formato(codigo):
        return False, "Codigo invalido. Formato esperado: E001, E002, etc."
    if codigo_existe(codigo, lista_empleados):
        return False, f"El codigo {codigo} ya esta registrado."
    if not validar_nombre(nombres) or not validar_nombre(apellidos):
        return False, "Nombres y apellidos: solo letras y espacios (sin numeros ni simbolos como @)."
    if not validar_dni(dni):
        return False, "DNI invalido. Debe tener 8 digitos, sin repetir el mismo numero (00000000), sin secuencias (12345678) ni patrones repetidos."
    if dni_existe(lista_empleados, dni):
        return False, f"El DNI {dni.strip()} ya esta registrado en otro trabajador."
    if not validar_cargo(cargo):
        return False, "Cargo invalido. Use: Parrillero, Mesero, Caja, Cocina o Administracion."
    if not validar_turno(turno):
        return False, "Turno invalido. SG Aron's EIRL trabaja con 2 turnos: M (Mañana) o T (Tarde)."
    if not validar_tarifa_hora(tarifa_hora):
        return False, f"Tarifa por hora invalida. Debe ser mayor que 0 y hasta {MAX_TARIFA_HORA} soles, con maximo 2 decimales (ej: 8.5)."

    nuevo_empleado = {
        "codigo": codigo,
        "nombres": nombres.strip().title(),
        "apellidos": apellidos.strip().title(),
        "dni": dni.strip(),
        "cargo": cargo.strip().title(),
        "turno": normalizar_turno(turno),  # turno habitual
        "tarifa_hora": round(float(tarifa_hora), 2),
        "estado": "Activo",
    }
    lista_empleados.append(nuevo_empleado)
    return True, f"Empleado {codigo} registrado correctamente."


def modificar_empleado(lista_empleados, codigo, nombres, apellidos, dni, cargo, turno, tarifa_hora):
    """
    Modifica los datos de un trabajador ACTIVO (el codigo no se puede cambiar).
    Aplica las mismas validaciones que el registro; el DNI puede quedarse igual
    pero no puede coincidir con el de otro trabajador.
    Retorna (True, mensaje) o (False, mensaje_error). El mensaje resume que cambio
    (sirve para el historial de auditoria).
    """
    empleado = buscar_empleado_por_codigo(lista_empleados, codigo)
    if empleado is None:
        return False, f"No existe un trabajador con el codigo {codigo.strip().upper()}."
    if empleado["estado"] != "Activo":
        return False, f"El trabajador {empleado['codigo']} esta dado de baja y no se puede modificar."
    if not validar_nombre(nombres) or not validar_nombre(apellidos):
        return False, "Nombres y apellidos: solo letras y espacios (sin numeros ni simbolos como @)."
    if not validar_dni(dni):
        return False, "DNI invalido. Debe tener 8 digitos, sin repetir el mismo numero (00000000), sin secuencias (12345678) ni patrones repetidos."
    otros = [e for e in lista_empleados if e is not empleado]
    if dni_existe(otros, dni):
        return False, f"El DNI {dni.strip()} ya esta registrado en otro trabajador."
    if not validar_cargo(cargo):
        return False, "Cargo invalido. Use: Parrillero, Mesero, Caja, Cocina o Administracion."
    if not validar_turno(turno):
        return False, "Turno invalido. SG Aron's EIRL trabaja con 2 turnos: M (Mañana) o T (Tarde)."
    if not validar_tarifa_hora(tarifa_hora):
        return False, f"Tarifa por hora invalida. Debe ser mayor que 0 y hasta {MAX_TARIFA_HORA} soles, con maximo 2 decimales (ej: 8.5)."

    nuevos = {
        "nombres": nombres.strip().title(),
        "apellidos": apellidos.strip().title(),
        "dni": dni.strip(),
        "cargo": cargo.strip().title(),
        "turno": normalizar_turno(turno),
        "tarifa_hora": round(float(tarifa_hora), 2),
    }
    cambios = []
    for campo, valor in nuevos.items():
        if str(empleado[campo]) != str(valor):
            cambios.append(f"{campo}: {empleado[campo]} -> {valor}")
            empleado[campo] = valor
    if not cambios:
        return True, f"Trabajador {empleado['codigo']} sin cambios."
    return True, f"Trabajador {empleado['codigo']} modificado ({'; '.join(cambios)})."


def eliminar_empleado(lista_empleados, lista_asistencias, codigo):
    """
    Elimina a un trabajador:
      - si NO tiene asistencias, se borra de la lista;
      - si YA tiene asistencias, se le da de BAJA (estado 'Inactivo') para no perder
        el historial ni dejar asistencias huerfanas. Un inactivo no sale en la planilla
        ni puede marcar entrada.
    Retorna (True, mensaje) o (False, mensaje_error).
    """
    empleado = buscar_empleado_por_codigo(lista_empleados, codigo)
    if empleado is None:
        return False, f"No existe un trabajador con el codigo {codigo.strip().upper()}."
    if empleado["estado"] != "Activo":
        return False, f"El trabajador {empleado['codigo']} ya esta dado de baja."
    tiene_historial = any(a["codigo_empleado"] == empleado["codigo"] for a in lista_asistencias)
    if tiene_historial:
        empleado["estado"] = "Inactivo"
        return True, f"Trabajador {empleado['codigo']} dado de baja (conserva su historial de asistencias)."
    lista_empleados.remove(empleado)
    return True, f"Trabajador {empleado['codigo']} eliminado."


def listar_empleados(lista_empleados):
    """Retorna la lista de empleados (arreglo) tal como esta almacenada."""
    return lista_empleados


def buscar_empleado_por_codigo(lista_empleados, codigo):
    """Busqueda lineal por codigo. Retorna el diccionario del empleado o None."""
    codigo = codigo.strip().upper()
    for empleado in lista_empleados:
        if empleado["codigo"] == codigo:
            return empleado
    return None


def ordenar_empleados_por_codigo(lista_empleados):
    """
    Ordena los empleados por codigo (ascendente) con sorted() de Python
    (algoritmo Timsort, O(n log n)). Retorna una lista nueva: no modifica la original.
    """
    return sorted(lista_empleados, key=lambda empleado: empleado["codigo"])


def buscar_binario_recursivo(lista_ordenada, codigo, inicio=0, fin=None):
    """
    Busqueda binaria RECURSIVA por codigo.
    Requiere que 'lista_ordenada' este previamente ordenada por codigo
    (usar ordenar_empleados_por_codigo antes de llamar esta funcion).
    Caso base: rango vacio (no encontrado) o coincidencia encontrada.
    """
    codigo = codigo.strip().upper()
    if fin is None:
        fin = len(lista_ordenada) - 1

    if inicio > fin:
        return None  # caso base: no encontrado

    medio = (inicio + fin) // 2
    codigo_medio = lista_ordenada[medio]["codigo"]

    if codigo_medio == codigo:
        return lista_ordenada[medio]  # caso base: encontrado
    elif codigo_medio < codigo:
        return buscar_binario_recursivo(lista_ordenada, codigo, medio + 1, fin)
    else:
        return buscar_binario_recursivo(lista_ordenada, codigo, inicio, medio - 1)
