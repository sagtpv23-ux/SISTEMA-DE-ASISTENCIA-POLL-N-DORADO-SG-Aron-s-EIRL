# -*- coding: utf-8 -*-
"""
Todo lo que el usuario VE o ESCRIBE en la terminal.
"""

import getpass

CANCELAR = "cancelar"
AYUDA_CANCELAR = "(escriba 'cancelar' para volver al menu)"


#  entrada de datos
def pedir_opcion():
    return input("Elige una opcion: ").strip()


def pedir_dato(mensaje, validar, permitir_vacio=False, recortar=True):
    """
    Pide un dato y REPITE la pregunta hasta que sea valido (bucle while).
    validar(valor) devuelve None si el dato es correcto o el texto del error.
    Retorna el dato, '' si esta permitido dejarlo vacio, o None si escribe 'cancelar'.
    recortar=False conserva los espacios del inicio y del final (para que la regla
    pueda rechazarlos, por ejemplo en el nombre de usuario).
    """
    while True:
        valor = input(mensaje + " ")
        if recortar:
            valor = valor.strip()
        if valor.strip().lower() == CANCELAR:
            return None
        if valor.strip() == "" and permitir_vacio:
            return ""
        error = validar(valor)
        if error is None:
            return valor
        print(f"   Dato invalido: {error}")


def pedir_secreto(mensaje, validar=None):
    """
    Como pedir_dato pero SIN mostrar lo que se escribe (contraseñas), con getpass.
    validar(valor) devuelve None si es correcto o el texto del error (opcional).
    Retorna el texto, o None si escribe 'cancelar'.
    """
    while True:
        valor = getpass.getpass(mensaje + " ")
        if valor.strip().lower() == CANCELAR:
            return None
        error = validar(valor) if validar else None
        if error is None:
            return valor
        print(f"   Dato invalido: {error}")


def pedir_varios(preguntas):
    """
    preguntas: lista de (mensaje, regla, permitir_vacio) o (mensaje, regla, permitir_vacio, recortar).
    Retorna la lista de respuestas validas, o None si el usuario cancela.
    """
    print(AYUDA_CANCELAR)
    respuestas = []
    for pregunta in preguntas:
        mensaje, regla_dato, permitir_vacio, *resto = pregunta
        valor = pedir_dato(mensaje, regla_dato, permitir_vacio, resto[0] if resto else True)
        if valor is None:
            print("Operacion cancelada.")
            return None
        respuestas.append(valor)
    return respuestas


# salida de datos
def mostrar_mensaje(texto):
    print(texto)


def mostrar_menu(usuario=None, opciones=None):
    """
    Muestra el menu. 'opciones' es el conjunto de numeros que el rol puede usar
    (por ejemplo {"4", "5", "6"}); si es None se muestran todas.
    """
    def ver(numero):
        return opciones is None or numero in opciones

    print("\n===== SISTEMA DE ASISTENCIA - SG ARON'S EIRL =====")
    if usuario:
        print(f"Sesion: {usuario['usuario']} ({usuario['rol']})")
    lineas = [
        ("1", "1. Registrar trabajador"),
        ("2", "2. Listar trabajadores"),
        ("3", "3. Buscar trabajador por codigo"),
        ("4", "4. Marcar entrada"),
        ("5", "5. Marcar salida"),
        ("6", "6. Ver asistencias de un trabajador"),
        ("7", "7. Ver todas las asistencias ordenadas por fecha"),
        ("8", "8. Contar tardanzas totales"),
        ("9", "9. Generar planilla mensual (pago por horas)"),
        ("10", "10. Exportar reporte a Excel"),
    ]
    solo_admin = [
        ("11", "11. Modificar trabajador"),
        ("12", "12. Eliminar trabajador"),
        ("13", "13. Ver historial de auditoria"),
        ("14", "14. Crear usuario"),
    ]
    for numero, texto in lineas:
        if ver(numero):
            print(texto)
    if any(ver(numero) for numero, _ in solo_admin):
        print("--- Solo Administrador ---")
        for numero, texto in solo_admin:
            if ver(numero):
                print(texto)
    print("0. Cerrar sesion y salir")


def mostrar_auditoria(registros):
    """Tabla del historial: Fecha y hora | Usuario | Accion | Entidad | Detalle."""
    if not registros:
        print("No hay registros en el historial.")
        return
    print(f"{'Fecha y hora':<19} | {'Usuario':<12} | {'Accion':<13} | {'Entidad':<11} | Detalle")
    print("-" * 90)
    for r in registros:
        print(f"{r['fecha_hora']:<19} | {r['usuario']:<12} | {r['accion']:<13} | {r['entidad']:<11} | {r['detalle']}")


def mostrar_trabajadores(empleados):
    if not empleados:
        print("No hay trabajadores registrados.")
    for e in empleados:
        baja = "" if e.get("estado", "Activo") == "Activo" else f" [{e['estado'].upper()}]"
        print(
            f"{e['codigo']} - {e['nombres']} {e['apellidos']} - {e['cargo']} - "
            f"{e['turno']} - S/ {e['tarifa_hora']} por hora{baja}"
        )


def mostrar_trabajador_encontrado(e):
    print(
        f"Encontrado: {e['codigo']} - {e['nombres']} "
        f"{e['apellidos']} ({e['cargo']}, turno {e['turno']})"
    )


def mostrar_asistencia(r):
    """Imprime un registro de asistencia en una linea legible."""
    salida = r["hora_salida"] if r["hora_salida"] else "--:--"
    horas = r["horas_trabajadas"] if r["horas_trabajadas"] != "" else "-"
    print(
        f"{r['fecha']} | {r['codigo_empleado']} | {r['turno']:<6} | "
        f"{r['hora_entrada']} - {salida} | {horas} h | Tardanza: {r['tardanza']}"
    )


def mostrar_asistencias(registros, mensaje_vacio):
    if not registros:
        print(mensaje_vacio)
    for r in registros:
        mostrar_asistencia(r)


def mostrar_planilla(planilla, mes, total, avisos, meses_con_datos):
    """
    planilla: lista de dicts (uno por trabajador). avisos: {codigo: texto} que explican
    por que alguien sale en 0. meses_con_datos: lista de meses (vacia = no se muestra).
    """
    if not planilla:
        print("No hay trabajadores activos registrados.")
    for p in planilla:
        print(
            f"{p['codigo']} - {p['nombres']} {p['apellidos']}: "
            f"Mañana {p['horas_manana']} h + Tarde {p['horas_tarde']} h = "
            f"{p['horas_trabajadas']} h x S/ {p['tarifa_hora']} = S/ {p['pago_mensual']}"
        )
        if p["codigo"] in avisos:
            print(f"   Aviso: {avisos[p['codigo']]}")
    print(f"TOTAL PLANILLA {mes}: S/ {total}")
    if meses_con_datos:
        print("Meses con asistencias registradas: " + ", ".join(meses_con_datos))
