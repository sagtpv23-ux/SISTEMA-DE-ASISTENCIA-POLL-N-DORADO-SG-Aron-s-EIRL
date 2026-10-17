"""
Modulo de trabajadores.
Tiene las funciones para registrar, listar,
buscar y ordenar la lista de empleados con busquea lineal,
binaria y burbuja.
"""

from modulo_validaciones import(
    normalizar_turno,
    validar_codigo_formato,
    validar_dni,
    validar_texto_no_vacio,
    validar_cargo,
    validar_turno,
    validar_tarifa_hora,
    codigo_existe,
)

def registrar_empleado(lista_empleados, codigo,nombres, apellidos, dni, cargo, turno, tarifa_hora):
    "Reguistra un nuevo empleado tras validar todos sus datos requeridos."
    codigo = codigo.strip().upper()

    if not validar_codigo_formato(codigo):
        return False, "codigo invalido. Formato esperado: E001, E002, etc."
    if codigo_existe(codigo, lista_empleados):
        return False, f"El codigo{codigo} ya esta registrado."
    if not validar_texto_no_vacio(nombres) or not validar_texto_no_vacio(apellidos):
        return False, "Nombres y apellidos no pueden estar vacios."
    if not validar_dni(dni):
        return False, "DNI invalido. debe tener 8 digitos."
    if not validar_cargo(cargo):
        return False, "Cargo invalido. Use: Perrillero, Mesero, caja, Cocina o Administrador."
    if not validar_turno(turno):
        return False, "Turno invalido, SG Aron's EIRL travaja con 2 turnos: M (Mañana) o T (Tarde)."
    if not validar_tarifa_hora(tarifa_hora):
        return False, "Tarifa por hora invalida. Deve ser un numero positivo (ej: 8.5)."

    nuevo_empleado = {
        "codigo": codigo,
        "nombres": nombres.strip().title(),
        "apellidos": apellidos.strip().title(),
        "dni": dni.strip(),
        "cargo": cargo.strip().title(),
        "turno": normalizar_turno(turno), #turno habitual
        "tarifa_hora": round(float(tarifa_hora), 2),
        "estado": "Activo",
    }
    lista_empleados.append(nuevo_empleado)
    return True, f"Empleado {codigo} registrado correctamente."


def listar_empleados(lista_empleados):
    """Retorna la lista de empleados (arreglo) tal como esta almacenada."""
    return lista_empleados

def buscar_empleado_por_codigo(lista_empleados, codigo):
    """Busqueda lineal por codigo. Retorna el Diccionario del empleado o None."""
    codigo = codigo.strip().upper()
    for empleado in lista_empleados:
        if empleado["codigo"] == codigo:
            return empleado
    return None
def ordenar_empleados_por_codigo(lista_empleados):
    """
    Algoritmo de ordenamiento burbuja (manual, sin usar sorted())
    para ordenar el arreglo de los empleados por codigo de menor a mayor.
    """
    n = len(lista_empleados)
    lista_ordenada = lista_empleados.copy()
    for i in range(n - 1):
        for j in range(n - 1 - i):
            if lista_ordenada[j]["codigo"] > lista_ordenada[j + 1]["codigo"]:
                lista_ordenada[j], lista_ordenada[j + 1] = (
                    lista_ordenada[j + 1],
                    lista_ordenada[j],
                )
    return lista_ordenada

def buscar_binario_recursivo(lista_ordenada, codigo, inicio=0, fin=None):
    """
    Busqueda binaria RECURSIVA por codigo.
    Requiere que 'lista_ordenada' este previamente ordenado por codigo
    (usar ordenar_empleados_por_codigo antes de llamar esta funcion).
    Caso base: rango vacio (no encontrado) o coincidencia encontrada.
    """
    codigo = codigo.strip().upper()
    if fin is None:
        fin = len(lista_ordenada) - 1

    if inicio > fin:
        return None #caso base: no encontrado
    medio = (inicio + fin) // 2
    codigo_medio = lista_ordenada[medio]["codigo"]

    if codigo_medio == codigo:
        return lista_ordenada[medio] # caso base: encontrado
    elif codigo_medio < codigo:
        return buscar_binario_recursivo(lista_ordenada, codigo, medio + 1, fin)
    else:
        return buscar_binario_recursivo(lista_ordenada, codigo, inicio, medio - 1)