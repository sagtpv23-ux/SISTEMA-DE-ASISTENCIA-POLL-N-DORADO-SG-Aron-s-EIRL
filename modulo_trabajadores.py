"Modulo de trabajadores."
"Tiene las funciones para registrar,"
"listar, buscar y ordenar la lista de empleados con busquea lineal,"
" binaria y burbuja."

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
    