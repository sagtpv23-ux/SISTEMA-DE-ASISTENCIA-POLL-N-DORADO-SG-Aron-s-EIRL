# -*- coding: utf-8 -*-
"""
CONTROLADOR (consola) - Logica de interaccion del menu.

Recibe lo que el usuario elige, pide los datos a la VISTA (views/consola.py),
llama a los MODELOS (models/) para validar, calcular y guardar, y devuelve el
resultado a la vista. No imprime ni lee del teclado directamente.
"""

from models.empleado import (
    registrar_empleado,
    modificar_empleado,
    eliminar_empleado,
    buscar_empleado_por_codigo,
    listar_empleados,
    ordenar_empleados_por_codigo,
    buscar_binario_recursivo,
    dni_existe,
)
from models.asistencia import (
    marcar_entrada,
    marcar_salida,
    buscar_asistencias_por_codigo,
    ordenar_asistencias_por_fecha,
    contar_tardanzas_recursivo,
    completar_turnos,
)
from models.base_datos import (
    guardar_empleados,
    cargar_empleados,
    guardar_asistencias,
    cargar_asistencias,
    cargar_usuarios,
    insertar_usuario,
)
from models.auditoria import registrar_auditoria, listar_auditoria
from models.usuarios import (
    MENSAJE_SIN_PERMISO,
    ROL_ADMIN,
    ROL_TRABAJADOR,
    autenticar_con_rol,
    codigo_propio,
    crear_usuario,
    error_nombre,
    error_usuario,
    es_administrador,
    hay_usuarios,
    rol_elegido,
    tiene_permiso,
    validar_contrasena,
)
from models.planilla import (
    generar_planilla_mensual,
    total_planilla,
    contar_jornadas_mes,
    meses_con_datos,
)
from models.validaciones import (
    MAX_TARIFA_HORA,
    codigo_existe,
    normalizar_hora,
    validar_cargo,
    validar_codigo_formato,
    validar_dni,
    validar_formato_fecha,
    validar_formato_mes,
    validar_nombre,
    validar_tarifa_hora,
    validar_turno,
)
from views import consola as vista
from views.reporte_excel import exportar_a_excel

MAX_INTENTOS_LOGIN = 3
# Permiso que necesita cada opcion del menu (los permisos de cada rol estan en models/usuarios.py)
PERMISO_POR_OPCION = {
    "1": "trabajadores", "2": "trabajadores", "3": "trabajadores",
    "4": "asistencia", "5": "asistencia", "6": "asistencia", "7": "asistencia", "8": "asistencia",
    "9": "reportes", "10": "reportes",
    "11": "trabajadores", "12": "trabajadores",
    "13": "auditoria", "14": "usuarios",
}

# Usuario con la sesion iniciada (lo fija iniciar_sesion; lo leen las opciones para auditar)
SESION = {"usuario": None}


def usuario_actual():
    u = SESION["usuario"]
    return u["usuario"] if u else None


SIN_VINCULO = "Tu usuario no esta vinculado a un trabajador. Pidele al Administrador que lo vincule."


def _codigo_de_sesion():
    """None si es Administrador (puede elegir el trabajador); el codigo vinculado si es Trabajador ('' si no tiene)."""
    usuario = SESION["usuario"]
    if es_administrador(usuario):
        return None
    return codigo_propio(usuario) or ""


def opciones_permitidas():
    """Numeros del menu que el rol de la sesion puede usar (los demas no se muestran)."""
    return {o for o, permiso in PERMISO_POR_OPCION.items() if tiene_permiso(SESION["usuario"], permiso)}


def auditar(accion, entidad, detalle=""):
    """Anota en el historial QUIEN hizo QUE y CUANDO (la fecha y hora las pone el modelo)."""
    registrar_auditoria(usuario_actual(), accion, entidad, detalle)


# ---------------------------------------------------------------- reglas de captura
def regla(condicion, error):
    """Crea una regla: devuelve None si el dato cumple la condicion o el mensaje de error."""
    return lambda valor: None if condicion(valor) else error


REGLA_CODIGO_FORMATO = regla(validar_codigo_formato, "use la letra E y 3 digitos (ej: E001).")
REGLA_NOMBRE = regla(validar_nombre, "solo letras y espacios (sin numeros ni simbolos como @).")
REGLA_DNI = regla(validar_dni, "use 8 digitos que no sean repetidos (00000000) ni secuencia (12345678).")
REGLA_CARGO = regla(validar_cargo, "use Parrillero, Mesero, Caja, Cocina o Administracion.")
REGLA_TURNO = regla(validar_turno, "use M (Mañana) o T (Tarde).")
REGLA_TARIFA = regla(validar_tarifa_hora, f"debe ser mayor que 0 y hasta {MAX_TARIFA_HORA}, con maximo 2 decimales (ej: 8.5).")
REGLA_FECHA = regla(validar_formato_fecha, "use AAAA-MM-DD con una fecha real (ej: 2026-09-01).")
REGLA_HORA = regla(lambda v: normalizar_hora(v) is not None, "use HH:MM en 24 horas (ej: 08:30).")
REGLA_MES = regla(validar_formato_mes, "use AAAA-MM (ej: 2026-09).")


def regla_codigo_nuevo(lista_empleados):
    """El codigo debe tener formato valido y no estar registrado."""
    def validar(valor):
        if not validar_codigo_formato(valor):
            return "use la letra E y 3 digitos (ej: E001)."
        if codigo_existe(valor, lista_empleados):
            return f"el codigo {valor.strip().upper()} ya esta registrado."
        return None
    return validar


def regla_dni_nuevo(lista_empleados):
    """El DNI debe ser valido (8 digitos con aspecto real) y no estar ya registrado."""
    def validar(valor):
        if not validar_dni(valor):
            return "use 8 digitos que no sean repetidos (00000000) ni secuencia (12345678)."
        if dni_existe(lista_empleados, valor):
            return f"el DNI {valor.strip()} ya esta registrado en otro trabajador."
        return None
    return validar


def regla_codigo_existente(lista_empleados):
    """El codigo debe tener formato valido y pertenecer a un trabajador registrado."""
    def validar(valor):
        if not validar_codigo_formato(valor):
            return "use la letra E y 3 digitos (ej: E001)."
        if not codigo_existe(valor, lista_empleados):
            return f"no existe un trabajador con el codigo {valor.strip().upper()}."
        return None
    return validar


REGLA_NOMBRE_COMPLETO = error_nombre   # nombres y apellidos: sin numeros ni simbolos, al menos 2 palabras
REGLA_USUARIO = error_usuario   # devuelve el motivo exacto del error (espacios, primera letra, largo, simbolos)
REGLA_ROL = regla(lambda v: v.strip().upper() in ("A", "T"), "use A (Administrador) o T (Trabajador).")
REGLA_SI_NO = regla(lambda v: v.strip().upper() in ("SI", "NO"), "escriba SI o NO.")


# ---------------------------------------------------------------- autenticacion
def crear_primer_administrador(lista_usuarios):
    """Primera vez: no hay usuarios, asi que se crea el Administrador inicial (sin claves por defecto)."""
    vista.mostrar_mensaje("Primera ejecucion: cree el usuario Administrador.")
    datos = vista.pedir_varios([
        ("Usuario (ej: admin):", REGLA_USUARIO, False, False),
        ("Nombre completo (nombres y apellidos):", REGLA_NOMBRE_COMPLETO, False),
    ])
    if datos is None:
        return None
    usuario, nombre = datos
    clave = _pedir_clave_nueva(usuario)
    if clave is None:
        return None
    ok, mensaje = crear_usuario(lista_usuarios, usuario, nombre, ROL_ADMIN, clave)
    vista.mostrar_mensaje(mensaje)
    if not ok or not insertar_usuario(lista_usuarios[-1]):
        return None
    SESION["usuario"] = {"usuario": lista_usuarios[-1]["usuario"], "nombre": lista_usuarios[-1]["nombre"],
                         "rol": ROL_ADMIN}
    auditar("Insertar", "Usuario", f"Administrador inicial {usuario}")
    return SESION["usuario"]


def _pedir_clave_nueva(usuario):
    """Pide la contraseña dos veces (oculta). Retorna la clave o None si cancela."""
    while True:
        clave = vista.pedir_secreto("Contraseña (min. 8, con letras y numeros):",
                                    lambda v: validar_contrasena(v, usuario))
        if clave is None:
            return None
        repetida = vista.pedir_secreto("Repita la contraseña:")
        if repetida is None:
            return None
        if clave == repetida:
            return clave
        vista.mostrar_mensaje("   Las contraseñas no coinciden. Intente de nuevo.")


def iniciar_sesion(lista_usuarios):
    """
    Pide el rol (A=Administrador / T=Trabajador), el usuario y la contraseña (maximo
    MAX_INTENTOS_LOGIN intentos). Retorna el usuario autenticado (sin hash) o None.
    Todo intento fallido queda en la auditoria y el mensaje no dice si fallo el rol,
    el usuario o la contraseña. El rol real sale de la base de datos.
    """
    if not hay_usuarios(lista_usuarios):
        return crear_primer_administrador(lista_usuarios)
    vista.mostrar_mensaje("===== INICIAR SESION =====")
    for _ in range(MAX_INTENTOS_LOGIN):
        rol_login = rol_elegido(input("Ingresar como (A=Administrador / T=Trabajador): "))
        usuario = input("Usuario: ").strip().lower()
        clave = vista.pedir_secreto("Contraseña:")
        if clave is None:
            return None
        encontrado = None if rol_login is None else autenticar_con_rol(lista_usuarios, usuario, clave, rol_login)
        if encontrado:
            SESION["usuario"] = encontrado
            auditar("Login", "Sesion", "Inicio de sesion (consola)")
            vista.mostrar_mensaje(f"Bienvenido/a, {encontrado['nombre']} ({encontrado['rol']}).")
            return encontrado
        registrar_auditoria(usuario[:20] or "(vacio)", "Login fallido", "Sesion", "Credenciales o rol incorrectos (consola)")
        vista.mostrar_mensaje("Usuario, contraseña o rol incorrectos.")
    vista.mostrar_mensaje("Demasiados intentos fallidos. El programa se cerrara.")
    return None


# ---------------------------------------------------------------- una funcion por opcion
def opcion_registrar(lista_empleados):
    datos = vista.pedir_varios([
        ("Codigo (ej: E001):", regla_codigo_nuevo(lista_empleados), False),
        ("Nombres:", REGLA_NOMBRE, False),
        ("Apellidos:", REGLA_NOMBRE, False),
        ("DNI (8 digitos):", regla_dni_nuevo(lista_empleados), False),
        ("Cargo (Parrillero/Mesero/Caja/Cocina/Administracion):", REGLA_CARGO, False),
        ("Turno habitual (M=Mañana / T=Tarde):", REGLA_TURNO, False),
        ("Tarifa por hora en soles (ej: 8.5):", REGLA_TARIFA, False),
    ])
    if datos is None:
        return
    ok, mensaje = registrar_empleado(lista_empleados, *datos)
    vista.mostrar_mensaje(mensaje)
    if ok:
        guardar_empleados(lista_empleados)
        auditar("Insertar", "Trabajador", mensaje)


def opcion_listar(lista_empleados):
    vista.mostrar_trabajadores(listar_empleados(lista_empleados))


def opcion_buscar(lista_empleados):
    datos = vista.pedir_varios([("Codigo a buscar (ej: E001):", REGLA_CODIGO_FORMATO, False)])
    if datos is None:
        return
    # La busqueda binaria requiere la lista ordenada por codigo
    ordenados = ordenar_empleados_por_codigo(lista_empleados)
    resultado = buscar_binario_recursivo(ordenados, datos[0])
    auditar("Buscar", "Trabajador", f"Codigo {datos[0].strip().upper()}: "
            + ("encontrado" if resultado else "no encontrado"))
    if resultado:
        vista.mostrar_trabajador_encontrado(resultado)
    else:
        vista.mostrar_mensaje("Trabajador no encontrado.")


def opcion_entrada(lista_empleados, lista_asistencias):
    propio = _codigo_de_sesion()          # Trabajador: solo marca SU asistencia
    if propio == "":
        vista.mostrar_mensaje(SIN_VINCULO)
        return
    preguntas = [] if propio else [("Codigo del trabajador:", regla_codigo_existente(lista_empleados), False)]
    preguntas += [
        ("Fecha (AAAA-MM-DD):", REGLA_FECHA, False),
        ("Hora de entrada (HH:MM):", REGLA_HORA, False),
        ("Turno de la jornada (M/T, Enter = turno habitual):", REGLA_TURNO, True),
    ]
    datos = vista.pedir_varios(preguntas)
    if datos is None:
        return
    if propio:
        datos = [propio] + datos
    ok, mensaje = marcar_entrada(lista_asistencias, lista_empleados, *datos)
    vista.mostrar_mensaje(mensaje)
    if ok:
        guardar_asistencias(lista_asistencias)
        auditar("Insertar", "Asistencia", f"{mensaje} Fecha {datos[1]}.")


def opcion_salida(lista_empleados, lista_asistencias):
    propio = _codigo_de_sesion()
    if propio == "":
        vista.mostrar_mensaje(SIN_VINCULO)
        return
    preguntas = [] if propio else [("Codigo del trabajador:", regla_codigo_existente(lista_empleados), False)]
    preguntas += [
        ("Fecha (AAAA-MM-DD):", REGLA_FECHA, False),
        ("Hora de salida (HH:MM):", REGLA_HORA, False),
    ]
    datos = vista.pedir_varios(preguntas)
    if datos is None:
        return
    if propio:
        datos = [propio] + datos
    ok, mensaje = marcar_salida(lista_asistencias, *datos)
    vista.mostrar_mensaje(mensaje)
    if ok:
        guardar_asistencias(lista_asistencias)
        auditar("Modificar", "Asistencia", f"Salida de {datos[0].strip().upper()} el {datos[1]} a las {datos[2]}.")


def opcion_ver_asistencias(lista_empleados, lista_asistencias):
    propio = _codigo_de_sesion()
    if propio == "":
        vista.mostrar_mensaje(SIN_VINCULO)
        return
    if propio:                            # el Trabajador ve solo lo suyo, sin preguntar el codigo
        codigo = propio
    else:
        datos = vista.pedir_varios([("Codigo del trabajador:", regla_codigo_existente(lista_empleados), False)])
        if datos is None:
            return
        codigo = datos[0]
    registros = buscar_asistencias_por_codigo(lista_asistencias, codigo)
    vista.mostrar_asistencias(registros, "No hay registros para ese trabajador.")


def _asistencias_visibles(lista_asistencias):
    """Administrador: todas. Trabajador: solo las suyas (ninguna si su cuenta no esta vinculada)."""
    propio = _codigo_de_sesion()
    if propio is None:
        return lista_asistencias
    return buscar_asistencias_por_codigo(lista_asistencias, propio) if propio else []


def opcion_ordenar(lista_asistencias):
    vista.mostrar_asistencias(ordenar_asistencias_por_fecha(_asistencias_visibles(lista_asistencias)),
                              "No hay asistencias registradas.")


def opcion_tardanzas(lista_asistencias):
    vista.mostrar_mensaje(f"Total de tardanzas registradas: {contar_tardanzas_recursivo(_asistencias_visibles(lista_asistencias))}")


def opcion_planilla(lista_empleados, lista_asistencias):
    datos = vista.pedir_varios([("Mes (AAAA-MM, ej: 2026-09):", REGLA_MES, False)])
    if datos is None:
        return
    mes = datos[0]
    planilla = generar_planilla_mensual(lista_empleados, lista_asistencias, mes)
    total = total_planilla(planilla)
    avisos = {}
    for p in planilla:
        if p["horas_trabajadas"] == 0:
            # Explicar por que sale en cero (no es un error del programa)
            cerradas, abiertas = contar_jornadas_mes(lista_asistencias, p["codigo"], mes)
            if abiertas:
                avisos[p["codigo"]] = f"{abiertas} jornada(s) sin hora de salida (use la opcion 5)."
            elif not cerradas:
                avisos[p["codigo"]] = f"este trabajador no tiene asistencias en {mes}."
    meses = meses_con_datos(lista_asistencias) if total == 0 and lista_asistencias else []
    vista.mostrar_planilla(planilla, mes, total, avisos, meses)


def opcion_exportar(lista_empleados, lista_asistencias):
    """Exporta el reporte del mes. La exportacion es solo a Excel."""
    datos = vista.pedir_varios([
        ("Mes de la planilla a incluir (AAAA-MM):", REGLA_MES, False),
    ])
    if datos is None:
        return
    mes = datos[0]
    planilla = generar_planilla_mensual(lista_empleados, lista_asistencias, mes)
    ruta = exportar_a_excel(lista_empleados, lista_asistencias, planilla=planilla)
    if ruta:
        vista.mostrar_mensaje(f"Reporte generado: {ruta}")
        auditar("Exportar", "Reporte", f"Planilla {mes}: Excel")


# ---------------------------------------------------------------- opciones de Administrador
def opcion_modificar(lista_empleados):
    datos = vista.pedir_varios([("Codigo del trabajador a modificar:", regla_codigo_existente(lista_empleados), False)])
    if datos is None:
        return
    e = buscar_empleado_por_codigo(lista_empleados, datos[0])
    vista.mostrar_mensaje("Deje vacio (Enter) para conservar el valor actual.")
    nuevos = vista.pedir_varios([
        (f"Nombres [{e['nombres']}]:", REGLA_NOMBRE, True),
        (f"Apellidos [{e['apellidos']}]:", REGLA_NOMBRE, True),
        (f"DNI [{e['dni']}]:", REGLA_DNI, True),
        (f"Cargo [{e['cargo']}]:", REGLA_CARGO, True),
        (f"Turno habitual [{e['turno']}] (M/T):", REGLA_TURNO, True),
        (f"Tarifa por hora [{e['tarifa_hora']}]:", REGLA_TARIFA, True),
    ])
    if nuevos is None:
        return
    actuales = [e["nombres"], e["apellidos"], e["dni"], e["cargo"], e["turno"], e["tarifa_hora"]]
    valores = [str(nuevo if nuevo != "" else actual) for nuevo, actual in zip(nuevos, actuales)]
    ok, mensaje = modificar_empleado(lista_empleados, e["codigo"], *valores)
    vista.mostrar_mensaje(mensaje)
    if ok and "sin cambios" not in mensaje:
        guardar_empleados(lista_empleados)
        auditar("Modificar", "Trabajador", mensaje)


def opcion_eliminar(lista_empleados, lista_asistencias):
    datos = vista.pedir_varios([
        ("Codigo del trabajador a eliminar:", regla_codigo_existente(lista_empleados), False),
        ("¿Confirma? (SI/NO):", REGLA_SI_NO, False),
    ])
    if datos is None:
        return
    if datos[1].strip().upper() != "SI":
        vista.mostrar_mensaje("Operacion cancelada.")
        return
    ok, mensaje = eliminar_empleado(lista_empleados, lista_asistencias, datos[0])
    vista.mostrar_mensaje(mensaje)
    if ok:
        guardar_empleados(lista_empleados)
        auditar("Eliminar", "Trabajador", mensaje)


def opcion_auditoria():
    vista.mostrar_mensaje("Ultimos 50 movimientos (del mas reciente al mas antiguo):")
    vista.mostrar_auditoria(listar_auditoria(50))


def opcion_crear_usuario(lista_usuarios, lista_empleados=None):
    datos = vista.pedir_varios([
        ("Usuario nuevo:", REGLA_USUARIO, False, False),
        ("Nombre completo (nombres y apellidos):", REGLA_NOMBRE_COMPLETO, False),
        ("Rol (A=Administrador / T=Trabajador):", REGLA_ROL, False),
    ])
    if datos is None:
        return
    usuario, nombre, rol = datos
    rol = ROL_ADMIN if rol.strip().upper() == "A" else ROL_TRABAJADOR
    codigo = ""
    if rol == ROL_TRABAJADOR and lista_empleados is not None:
        # Una cuenta de Trabajador pertenece a un trabajador registrado (solo marcara SU asistencia)
        vinculo = vista.pedir_varios([("Codigo del trabajador de esta cuenta (ej: E001):",
                                       regla_codigo_existente(lista_empleados), False)])
        if vinculo is None:
            return
        codigo = vinculo[0]
    clave = _pedir_clave_nueva(usuario)
    if clave is None:
        vista.mostrar_mensaje("Operacion cancelada.")
        return
    ok, mensaje = crear_usuario(lista_usuarios, usuario, nombre, rol, clave, codigo, lista_empleados)
    if ok and not insertar_usuario(lista_usuarios[-1]):
        lista_usuarios.pop()
        ok, mensaje = False, "No se pudo guardar el usuario."
    vista.mostrar_mensaje(mensaje)
    if ok:
        auditar("Insertar", "Usuario", f"Usuario {usuario.strip().lower()} ({rol})")


# ---------------------------------------------------------------- programa principal
def main():
    lista_usuarios = cargar_usuarios()
    if iniciar_sesion(lista_usuarios) is None:
        return

    lista_empleados = cargar_empleados()
    lista_asistencias = cargar_asistencias()

    # Datos de versiones anteriores: asignar el turno habitual a jornadas sin turno
    antiguos = completar_turnos(lista_asistencias, lista_empleados)
    if antiguos:
        vista.mostrar_mensaje(f"Aviso: {antiguos} asistencia(s) de una version anterior no tenian turno;")
        vista.mostrar_mensaje("       se les asigno el turno habitual del trabajador.")

    acciones = {
        "1": lambda: opcion_registrar(lista_empleados),
        "2": lambda: opcion_listar(lista_empleados),
        "3": lambda: opcion_buscar(lista_empleados),
        "4": lambda: opcion_entrada(lista_empleados, lista_asistencias),
        "5": lambda: opcion_salida(lista_empleados, lista_asistencias),
        "6": lambda: opcion_ver_asistencias(lista_empleados, lista_asistencias),
        "7": lambda: opcion_ordenar(lista_asistencias),
        "8": lambda: opcion_tardanzas(lista_asistencias),
        "9": lambda: opcion_planilla(lista_empleados, lista_asistencias),
        "10": lambda: opcion_exportar(lista_empleados, lista_asistencias),
        "11": lambda: opcion_modificar(lista_empleados),
        "12": lambda: opcion_eliminar(lista_empleados, lista_asistencias),
        "13": lambda: opcion_auditoria(),
        "14": lambda: opcion_crear_usuario(lista_usuarios, lista_empleados),
    }

    try:
        while True:
            vista.mostrar_menu(SESION["usuario"], opciones_permitidas())
            opcion = vista.pedir_opcion()
            if opcion == "0":
                vista.mostrar_mensaje("Hasta luego.")
                break
            accion = acciones.get(opcion)
            if accion is None:
                vista.mostrar_mensaje("Opcion invalida.")
                continue
            if not tiene_permiso(SESION["usuario"], PERMISO_POR_OPCION[opcion]):
                vista.mostrar_mensaje(MENSAJE_SIN_PERMISO)
                continue
            accion()
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C o fin de la entrada: se sale ordenadamente sin perder datos
        vista.mostrar_mensaje("\nPrograma interrumpido por el usuario.")
    finally:
        guardar_empleados(lista_empleados)
        guardar_asistencias(lista_asistencias)
        auditar("Logout", "Sesion", "Cierre de sesion (consola)")
        SESION["usuario"] = None
