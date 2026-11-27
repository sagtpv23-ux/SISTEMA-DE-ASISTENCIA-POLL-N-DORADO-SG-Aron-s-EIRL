"""
Modulo de gestion de asistencia.
Cubre: marcar entrada/salida por turno, calculo de horas trabajadas,
busqueda por codigo, ordenamiento (seleccion) y conteo recursivo
de tardanzas.
"""

from datetime import datetime
from modulo_validaciones import (
    normalizar_turno,
    normalizar_hora,
    validar_formato_fecha,
    hora_es_posterior,
)

# SG Aron's EIRL trabaja con 2 turnos. Cada turno tiene su propia hora tope
# de entrada: una marcacion posterior al tope se registra como tardanza.
# (Valores de ejemplo: deben confirmarse con la gerencia del negocio.)
HORA_TOPE_POR_TURNO = {
    "Mañana": "08:00",
    "Tarde": "14:00",
}


def _buscar_registro_abierto(lista_asistencias, codigo, fecha):
    """Busca un registro del mismo empleado y fecha sin hora de salida aun."""
    for registro in lista_asistencias:
        if (
            registro["codigo_empleado"] == codigo
            and registro["fecha"] == fecha
            and registro["hora_salida"] == ""
        ):
            return registro
    return None


def marcar_entrada(lista_asistencias, lista_empleados, codigo, fecha, hora, turno=""):
    """
    Registra la hora de entrada de un empleado en una fecha dada.
    turno: 'M'/'T' (o nombre completo). Si se deja vacio se usa el turno
    habitual del trabajador; asi se registra cuando alguien cubre otro turno.
    """
    from modulo_trabajadores import buscar_empleado_por_codigo

    codigo = codigo.strip().upper()

    empleado = buscar_empleado_por_codigo(lista_empleados, codigo)
    if empleado is None:
        return False, f"No existe un empleado con codigo {codigo}."

    if turno.strip() == "":
        turno_jornada = empleado["turno"]
    else:
        turno_jornada = normalizar_turno(turno)
        if turno_jornada is None:
            return False, "Turno invalido. Use M (Mañana) o T (Tarde)."

    if not validar_formato_fecha(fecha):
        return False, "Fecha invalida. Formato esperado: AAAA-MM-DD."
    hora = normalizar_hora(hora)
    if hora is None:
        return False, "Hora invalida. Formato esperado: HH:MM."
    fecha = fecha.strip()
    if _buscar_registro_abierto(lista_asistencias, codigo, fecha) is not None:
        return False, "Ya existe una entrada sin salida registrada ese dia."

    # El tope depende del turno de ESTA jornada, no de un valor unico:
    # entrar a las 14:00 en el turno Tarde es puntual.
    tardanza = "Si" if hora > HORA_TOPE_POR_TURNO[turno_jornada] else "No"

    nuevo_registro = {
        "codigo_empleado": codigo,
        "fecha": fecha,
        "turno": turno_jornada,
        "hora_entrada": hora,
        "hora_salida": "",
        "horas_trabajadas": "",
        "tardanza": tardanza,
        "observaciones": "",
    }
    lista_asistencias.append(nuevo_registro)
    return True, f"Entrada registrada para {codigo} ({turno_jornada}) a las {hora}."


def marcar_salida(lista_asistencias, codigo, fecha, hora):
    """Registra la hora de salida y calcula las horas trabajadas."""
    codigo = codigo.strip().upper()
    fecha = fecha.strip()

    hora = normalizar_hora(hora)
    if hora is None:
        return False, "Hora invalida. Formato esperado: HH:MM."

    registro = _buscar_registro_abierto(lista_asistencias, codigo, fecha)
    if registro is None:
        return False, "No hay una entrada abierta para ese empleado en esa fecha."
    if not hora_es_posterior(registro["hora_entrada"], hora):
        return False, "La hora de salida debe ser posterior a la de entrada."

    registro["hora_salida"] = hora
    registro["horas_trabajadas"] = calcular_horas_trabajadas(
        registro["hora_entrada"], hora
    )
    return True, f"Salida registrada para {codigo} a las {hora}."


def calcular_horas_trabajadas(hora_entrada, hora_salida):
    """Calcula la diferencia en horas (con decimales) entre dos horas HH:MM."""
    fmt = "%H:%M"
    entrada = datetime.strptime(hora_entrada, fmt)
    salida = datetime.strptime(hora_salida, fmt)
    diferencia = salida - entrada
    return round(diferencia.total_seconds() / 3600, 2)


def buscar_asistencias_por_codigo(lista_asistencias, codigo):
    """Busqueda lineal: retorna todos los registros de un empleado."""
    codigo = codigo.strip().upper()
    return [r for r in lista_asistencias if r["codigo_empleado"] == codigo]


def ordenar_asistencias_por_fecha(lista_asistencias):
    """
    Ordenamiento por SELECCION (manual, sin sorted()): ordena los registros
    por fecha y, a igual fecha, por hora de entrada (orden ascendente).
    """
    n = len(lista_asistencias)
    lista_ordenada = lista_asistencias.copy()
    for i in range(n - 1):
        indice_menor = i
        for j in range(i + 1, n):
            clave_j = (lista_ordenada[j]["fecha"], lista_ordenada[j]["hora_entrada"])
            clave_menor = (
                lista_ordenada[indice_menor]["fecha"],
                lista_ordenada[indice_menor]["hora_entrada"],
            )
            if clave_j < clave_menor:
                indice_menor = j
        lista_ordenada[i], lista_ordenada[indice_menor] = (
            lista_ordenada[indice_menor],
            lista_ordenada[i],
        )
    return lista_ordenada


def contar_tardanzas_recursivo(lista_asistencias, inicio=0, fin=None):
    """
    Cuenta recursivamente los registros con tardanza = 'Si' dividiendo la lista
    en dos mitades (divide y venceras). La profundidad es de unos log2(n)
    niveles, asi que funciona con miles de registros sin superar el limite de
    recursion de Python (que es de ~1000 llamadas).
    Casos base: rango vacio (0) y rango de un solo registro.
    """
    if fin is None:
        fin = len(lista_asistencias) - 1
    if inicio > fin:
        return 0  # caso base: rango vacio
    if inicio == fin:  # caso base: un solo registro
        return 1 if lista_asistencias[inicio]["tardanza"] == "Si" else 0
    medio = (inicio + fin) // 2
    return (contar_tardanzas_recursivo(lista_asistencias, inicio, medio)
            + contar_tardanzas_recursivo(lista_asistencias, medio + 1, fin))


def completar_turnos(lista_asistencias, lista_empleados):
    """
    Los archivos de versiones anteriores no guardaban el turno de cada jornada.
    A esos registros se les asigna el turno habitual del trabajador (o Mañana
    si el trabajador ya no existe). Retorna cuantos registros se actualizaron.
    """
    from modulo_trabajadores import buscar_empleado_por_codigo

    actualizados = 0
    for registro in lista_asistencias:
        if registro.get("turno", "") == "":
            empleado = buscar_empleado_por_codigo(lista_empleados, registro["codigo_empleado"])
            if empleado is not None and empleado.get("turno"):
                registro["turno"] = empleado["turno"]
            else:
                registro["turno"] = "Mañana"
            actualizados += 1
    return actualizados
