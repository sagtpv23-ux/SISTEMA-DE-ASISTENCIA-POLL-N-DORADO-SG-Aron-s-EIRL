# -*- coding: utf-8 -*-
"""
MODELO - Usuarios y autenticacion (logica de negocio).

- Las contraseñas NUNCA se guardan: se guarda un hash PBKDF2-HMAC-SHA256 con una
  sal aleatoria distinta por usuario (solo libreria estandar: hashlib, hmac, secrets).
- Roles: Administrador (crear, editar, eliminar y ver todo) y Trabajador (solo ver y
  registrar SU PROPIA asistencia). Cada cuenta de Trabajador esta vinculada a un
  trabajador registrado (codigo_empleado): no puede marcar ni ver la asistencia de otros.
  Los permisos de cada rol estan en PERMISOS_POR_ROL.
- No hay usuario ni contraseña por defecto: el primer Administrador se crea la
  primera vez que se abre el sistema.
No depende de vistas ni controladores.
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime

from models.empleado import buscar_empleado_por_codigo
from models.validaciones import validar_codigo_formato, validar_nombre

ROL_ADMIN = "Administrador"
ROL_TRABAJADOR = "Trabajador"
ROL_SUPERADMIN_INTERNO = "SuperAdmin"  # Cuenta técnica; no se ofrece para creación desde la interfaz.
ROLES_VALIDOS = [ROL_ADMIN, ROL_TRABAJADOR]

# Que puede hacer cada rol. Consola y web consultan SIEMPRE esta tabla.
#   asistencia   : ver y registrar asistencia (el Administrador la de cualquier trabajador;
#                  el Trabajador SOLO la suya: ver codigo_propio y puede_ver_codigo)
#   trabajadores : administracion de trabajadores (registrar, listar, buscar, modificar, eliminar)
#   reportes     : planilla mensual y exportaciones (Excel, CSV, JSON)
#   auditoria    : historial de cambios
#   usuarios     : crear usuarios del sistema
PERMISOS_POR_ROL = {
    ROL_ADMIN: {"asistencia", "trabajadores", "reportes", "auditoria", "usuarios"},
    ROL_TRABAJADOR: {"asistencia"},
    ROL_SUPERADMIN_INTERNO: {"asistencia", "trabajadores", "reportes", "auditoria", "usuarios"},
}
MENSAJE_SIN_PERMISO = "No tienes permiso."

USUARIO_MIN = 4
USUARIO_MAX = 15
NOMBRE_MAX = 60

ITERACIONES = 200_000
MIN_LARGO_CLAVE = 8
MAX_LARGO_CLAVE = 128


# validaciones
def normalizar_usuario(usuario):
    return usuario.strip().lower()


def error_usuario(usuario):
    """
    Revisa el nombre de usuario TAL COMO LO ESCRIBIO la persona (sin recortarlo).
    Reglas: solo letras (A-Z, sin tildes ni ñ), numeros y guion bajo (_); debe empezar
    con una letra; de 4 a 15 caracteres; sin espacios ni caracteres raros.
    Retorna None si es valido o el texto del primer error encontrado.
    """
    if usuario == "":
        return "el usuario no puede estar vacio."
    if any(c.isspace() for c in usuario):
        return "el usuario no puede tener espacios."
    if re.fullmatch(r"[A-Za-z0-9_]+", usuario) is None:
        return "solo se permiten letras (sin tildes ni ñ), numeros y guion bajo (_); no use simbolos como @ - . ,"
    if not usuario[0].isalpha():
        return "el usuario debe empezar con una letra (no con un numero ni con _)."
    if not (USUARIO_MIN <= len(usuario) <= USUARIO_MAX):
        return f"el usuario debe tener entre {USUARIO_MIN} y {USUARIO_MAX} caracteres (escribio {len(usuario)})."
    return None


def validar_usuario(usuario):
    """True si el nombre de usuario cumple todas las reglas de error_usuario."""
    return error_usuario(usuario) is None


def error_nombre(nombre):
    """
    Nombre completo: exactamente 2 palabras (nombre y apellido), solo letras Unicode.
    Cada palabra debe tener al menos 2 letras. Se rechazan números, símbolos,
    iniciales sueltas (por ejemplo "A A"), espacios múltiples y más de 2 palabras.
    Retorna None si es valido o el texto del error.
    """
    texto = " ".join(nombre.split())
    if texto == "":
        return "escriba nombre y apellido (exactamente 2 palabras)."
    if len(texto) > NOMBRE_MAX:
        return f"no puede tener mas de {NOMBRE_MAX} caracteres."
    if not validar_nombre(texto):
        return "solo letras y un espacio entre nombre y apellido (sin numeros ni simbolos)."
    palabras = texto.split()
    if len(palabras) != 2:
        return "ingrese exactamente 2 palabras: nombre y apellido."
    if any(len(palabra) < 2 for palabra in palabras):
        return "cada palabra debe tener al menos 2 letras; no se aceptan iniciales como A A."
    return None


def validar_contrasena(clave, usuario=""):
    """
    Devuelve None si la contraseña es aceptable o el texto del error.
    Reglas: 8 a 128 caracteres, al menos una letra y un digito, y distinta del usuario.
    """
    if not (MIN_LARGO_CLAVE <= len(clave) <= MAX_LARGO_CLAVE):
        return f"debe tener entre {MIN_LARGO_CLAVE} y {MAX_LARGO_CLAVE} caracteres."
    if not any(c.isalpha() for c in clave) or not any(c.isdigit() for c in clave):
        return "debe incluir al menos una letra y un numero."
    if usuario and clave.strip().lower() == normalizar_usuario(usuario):
        return "no puede ser igual al nombre de usuario."
    return None


# ----------------------------------------------------------------- hash
def hashear_contrasena(clave, sal=None, iteraciones=ITERACIONES):
    """Retorna 'pbkdf2_sha256$iteraciones$sal$hash' (todo en texto hexadecimal)."""
    if sal is None:
        sal = secrets.token_bytes(16)
    resumen = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${sal.hex()}${resumen.hex()}"


def verificar_contrasena(clave, almacenado):
    """True si 'clave' corresponde al hash guardado (comparacion de tiempo constante)."""
    try:
        algoritmo, iteraciones, sal_hex, hash_hex = almacenado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        iteraciones_num = int(iteraciones)
        if not (100_000 <= iteraciones_num <= 1_000_000):
            return False
        sal = bytes.fromhex(sal_hex)
        hash_esperado = bytes.fromhex(hash_hex)
        if len(sal) != 16 or len(hash_esperado) != 32:
            return False
        calculado = hashlib.pbkdf2_hmac(
            "sha256", clave.encode("utf-8"), sal, iteraciones_num
        )
        return hmac.compare_digest(calculado.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# Hash de relleno: se usa cuando el usuario no existe, para que tardar lo mismo
# que con un usuario real y no revelar que usuarios existen.
_HASH_RELLENO = hashear_contrasena("relleno-no-valido-0")


#  operaciones
def hay_usuarios(lista_usuarios):
    return len(lista_usuarios) > 0


def buscar_usuario(lista_usuarios, usuario):
    usuario = normalizar_usuario(usuario)
    for u in lista_usuarios:
        if u["usuario"] == usuario:
            return u
    return None


def crear_usuario(lista_usuarios, usuario, nombre, rol, clave, codigo_empleado="", lista_empleados=None):
    """
    Agrega un usuario a la lista tras validar sus datos.
    Una cuenta de Trabajador debe estar VINCULADA a un trabajador registrado y activo
    (codigo_empleado) que no tenga ya otra cuenta; asi se sabe de quien es cada marcacion.
    Si no se entrega lista_empleados no se puede comprobar el vinculo (uso interno/pruebas).
    Retorna (True, mensaje) o (False, mensaje_error).
    """
    error = error_usuario(usuario)          # se valida lo escrito, sin recortar espacios
    if error:
        return False, f"Usuario invalido: {error}"
    usuario = normalizar_usuario(usuario)   # se guarda en minusculas (Juan_01 y juan_01 son el mismo usuario)
    if buscar_usuario(lista_usuarios, usuario) is not None:
        return False, f"El usuario {usuario} ya existe."
    error = error_nombre(nombre)
    if error:
        return False, f"Nombre invalido: {error}"
    if rol not in ROLES_VALIDOS:
        return False, f"Rol invalido. Use: {', '.join(ROLES_VALIDOS)}."
    codigo = ""
    if rol == ROL_TRABAJADOR and lista_empleados is not None:
        codigo = codigo_empleado.strip().upper()
        if not validar_codigo_formato(codigo):
            return False, "Escriba el codigo del trabajador al que pertenece esta cuenta (ej: E001)."
        empleado = buscar_empleado_por_codigo(lista_empleados, codigo)
        if empleado is None or empleado.get("estado", "Activo") != "Activo":
            return False, f"No existe un trabajador activo con el codigo {codigo}."
        if any(u.get("codigo_empleado", "") == codigo for u in lista_usuarios):
            return False, f"El trabajador {codigo} ya tiene una cuenta de usuario."
    elif rol == ROL_TRABAJADOR:
        codigo = codigo_empleado.strip().upper()
    error = validar_contrasena(clave, usuario)
    if error:
        return False, f"Contraseña invalida: {error}"
    lista_usuarios.append({
        "usuario": usuario,
        "nombre": " ".join(nombre.split()).title(),
        "rol": rol,
        "clave_hash": hashear_contrasena(clave),
        "creado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "codigo_empleado": codigo,
    })
    return True, f"Usuario {usuario} ({rol}) creado correctamente."


def autenticar(lista_usuarios, usuario, clave):
    """
    Retorna una copia del usuario SIN el hash si las credenciales son correctas, o None.
    El mensaje al usuario debe ser siempre el mismo ('usuario o contraseña incorrectos'),
    sin decir cual de los dos fallo.
    """
    encontrado = buscar_usuario(lista_usuarios, usuario)
    if encontrado is None:
        verificar_contrasena(clave, _HASH_RELLENO)  # mismo costo de tiempo
        return None
    if not verificar_contrasena(clave, encontrado["clave_hash"]):
        return None
    return {k: v for k, v in encontrado.items() if k != "clave_hash"}


def es_administrador(usuario):
    return usuario is not None and usuario.get("rol") in (ROL_ADMIN, ROL_SUPERADMIN_INTERNO)


def tiene_permiso(usuario, permiso):
    """True si el rol del usuario (diccionario de la sesion) incluye ese permiso."""
    if usuario is None:
        return False
    return permiso in PERMISOS_POR_ROL.get(usuario.get("rol"), set())


def codigo_propio(usuario):
    """Codigo del trabajador vinculado a la cuenta (solo Trabajador); None para el Administrador."""
    if usuario is None or es_administrador(usuario):
        return None
    return usuario.get("codigo_empleado", "") or None


def puede_ver_codigo(usuario, codigo):
    """
    Regla de asistencia: el Administrador puede ver y marcar la de cualquier trabajador;
    el Trabajador solo la de su propio codigo (y nunca si su cuenta no esta vinculada).
    """
    if usuario is None:
        return False
    if es_administrador(usuario):
        return True
    propio = codigo_propio(usuario)
    return propio is not None and codigo.strip().upper() == propio


def rol_elegido(valor):
    """
    Interpreta el rol que la persona elige al iniciar sesion: 'A' / 'T' (consola) o el
    nombre del rol (web). Retorna el rol o None si no es valido.
    """
    texto = valor.strip()
    por_letra = {"A": ROL_ADMIN, "T": ROL_TRABAJADOR}
    if texto.upper() in por_letra:
        return por_letra[texto.upper()]
    return next((r for r in ROLES_VALIDOS if r.lower() == texto.lower()), None)


def autenticar_con_rol(lista_usuarios, usuario, clave, rol=None):
    """
    Como autenticar, pero ademas exige que la cuenta sea del rol elegido en el login.
    El rol REAL siempre sale de la base de datos: elegir 'Administrador' no da permisos,
    solo confirma que la cuenta es de ese rol. Con rol=None no se comprueba (compatibilidad).
    Retorna el usuario (sin hash) o None.
    """
    encontrado = autenticar(lista_usuarios, usuario, clave)
    if encontrado is None or (rol is not None and encontrado["rol"] != rol):
        return None
    return encontrado
