# -*- coding: utf-8 -*-
"""
CONTROLADOR (web) - Logica de interaccion de la interfaz web (Flask).

Cada ruta recibe lo que el usuario envia desde el navegador, llama a los MODELOS
(models/) para validar, calcular y guardar, y elige la VISTA a mostrar: las paginas
views/templates/index.html y views/templates/login.html. Aqui no hay HTML ni reglas
de negocio.

Seguridad:
  - Hay que iniciar sesion para usar cualquier pagina (contraseñas con hash PBKDF2).
  - Cada formulario lleva un token CSRF; la cookie de sesion es HttpOnly y SameSite=Lax.
  - La clave que firma la sesion se genera al azar y se guarda en data/secret.key.
  - 5 intentos fallidos seguidos bloquean ese usuario durante 60 segundos.
  - Roles: el Administrador puede todo; el Trabajador solo ve y registra asistencia.
    Si un Trabajador intenta entrar a una parte de administrador (por el menu o
    escribiendo la direccion) ve "No tienes permiso." Los permisos estan en models/usuarios.py.

Asistencia (pantalla Marcar asistencia):
  - Las horas se muestran y se escriben en formato 12 h con AM/PM (se guardan en 24 h).
  - Para marcar ENTRADA o SALIDA hay que tener un turno elegido; la pantalla lo propone sola
    segun la hora, pero el servidor rechaza una marcacion sin turno.
  - Solo se admite la fecha de HOY: no se aceptan fechas pasadas ni futuras.
La exportacion de reportes es solo a Excel.
"""

import hmac
import os
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, session, url_for)

from models.asistencia import (
    HORA_TOPE_POR_TURNO,
    turno_segun_hora,
    buscar_asistencias_por_codigo,
    completar_turnos,
    contar_tardanzas_recursivo,
    marcar_entrada,
    marcar_salida,
    ordenar_asistencias_por_fecha,
)
from models.auditoria import registrar_auditoria, listar_auditoria
from models.base_datos import (
    CARPETA_DATA,
    cargar_asistencias,
    cargar_empleados,
    cargar_usuarios,
    guardar_asistencias,
    guardar_empleados,
    insertar_usuario,
)
from models.empleado import (
    buscar_binario_recursivo,
    buscar_empleado_por_codigo,
    eliminar_empleado,
    modificar_empleado,
    ordenar_empleados_por_codigo,
    registrar_empleado,
)
from models.planilla import contar_jornadas_mes, generar_planilla_mensual, total_planilla
from models.usuarios import (
    MENSAJE_SIN_PERMISO,
    ROL_ADMIN,
    ROL_SUPERADMIN_INTERNO,
    ROLES_VALIDOS,
    hashear_contrasena,
    autenticar_con_rol,
    codigo_propio,
    crear_usuario,
    es_administrador,
    hay_usuarios,
    puede_ver_codigo,
    rol_elegido,
    tiene_permiso,
)
from models.validaciones import (CARGOS_VALIDOS, TURNOS_VALIDOS, formatear_hora_12, normalizar_hora,
                                 normalizar_turno, validar_formato_mes)
from views.reporte_excel import exportar_a_excel

# Las paginas (HTML) estan en views/templates
CARPETA_PLANTILLAS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "views", "templates"
)

MAX_INTENTOS = 5          # intentos fallidos antes de bloquear
SEGUNDOS_BLOQUEO = 60
HORAS_SESION = 8
RUTAS_PUBLICAS = {"login", "configuracion_inicial"}


def _clave_secreta():
    """Carga una clave persistente o la crea; nunca usa una clave efimera silenciosamente."""
    configurada = os.environ.get("SG_ARONS_SECRET_KEY", "").strip()
    if len(configurada) >= 32:
        return configurada

    ruta = os.path.join(CARPETA_DATA, "secret.key")
    try:
        with open(ruta, encoding="utf-8") as archivo:
            clave = archivo.read().strip()
            if len(clave) >= 64:
                return clave
    except FileNotFoundError:
        pass

    clave = secrets.token_hex(32)
    os.makedirs(CARPETA_DATA, exist_ok=True)
    try:
        descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            archivo.write(clave)
    except FileExistsError:
        with open(ruta, encoding="utf-8") as archivo:
            clave = archivo.read().strip()
        if len(clave) < 64:
            raise RuntimeError("La clave de sesion almacenada no es valida.")
    except OSError as error:
        raise RuntimeError(
            "No se pudo guardar data/secret.key. Verifique permisos de escritura "
            "o configure SG_ARONS_SECRET_KEY."
        ) from error
    return clave


app = Flask(__name__, template_folder=CARPETA_PLANTILLAS)
app.secret_key = _clave_secreta()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Secure=False solo porque se sirve por HTTP en 127.0.0.1.
    # Al desplegar detras de HTTPS, cambiar a True.
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=HORAS_SESION),
    MAX_CONTENT_LENGTH=64 * 1024,
    MAX_FORM_MEMORY_SIZE=16 * 1024,
    MAX_FORM_PARTS=30,
)

# Mismas listas en memoria que usa el controlador de consola (se guardan en SQLite tras cada cambio)
empleados = cargar_empleados()
asistencias = cargar_asistencias()
completar_turnos(asistencias, empleados)

def _asegurar_superadmin_interno():
    """
    Garantiza una cuenta técnica interna, sin formulario ni credenciales por defecto.
    Puede provisionarse con SG_ARONS_SUPERADMIN_USER y SG_ARONS_SUPERADMIN_PASSWORD.
    Si no se configuran, genera credenciales aleatorias y conserva solo el hash.
    Nunca se muestra en la sección Usuarios ni en pantallas de configuración.
    """
    usuarios = cargar_usuarios()
    if any(u.get("rol") == ROL_SUPERADMIN_INTERNO for u in usuarios):
        return
    nombre = os.environ.get("SG_ARONS_SUPERADMIN_USER", "").strip().lower()
    clave = os.environ.get("SG_ARONS_SUPERADMIN_PASSWORD", "")
    if not nombre or not clave:
        nombre = "sys_" + secrets.token_hex(8)
        clave = secrets.token_urlsafe(48)
    registro = {
        "usuario": nombre,
        "nombre": "Sistema Interno",
        "rol": ROL_SUPERADMIN_INTERNO,
        "clave_hash": hashear_contrasena(clave),
        "creado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "codigo_empleado": "",
    }
    insertar_usuario(registro)


_asegurar_superadmin_interno()

intentos_fallidos = {}  # usuario -> (cantidad, instante del ultimo fallo)


# ------------------------------------------------------------------ sesion y permisos
def usuario_actual():
    return session.get("usuario")


def auditar(accion, entidad, detalle=""):
    """Anota en el historial quien hizo que (la fecha y hora las pone el modelo)."""
    u = usuario_actual()
    registrar_auditoria(u["usuario"] if u else None, accion, entidad, detalle)


def requiere_permiso(permiso):
    """Decorador: la ruta solo la puede usar un rol que tenga ese permiso (ver models/usuarios.py)."""
    def decorador(funcion):
        @wraps(funcion)
        def envoltura(*args, **kwargs):
            if not tiene_permiso(usuario_actual(), permiso):
                flash(MENSAJE_SIN_PERMISO, "error")
                return redirect(url_for("inicio"))
            return funcion(*args, **kwargs)
        return envoltura
    return decorador


# Permiso que necesita cada pestaña de la pagina
PERMISO_POR_VISTA = {
    "panel": "reportes",
    "trabajadores": "trabajadores", "editar": "trabajadores",
    "asistencia": "asistencia",
    "planilla": "reportes",
    "auditoria": "auditoria",
    "usuarios": "usuarios",
}


def vista_inicial():
    """Pantalla con la que empieza cada rol: el Administrador en su panel de Inicio y el Trabajador en Asistencia."""
    return "panel" if tiene_permiso(usuario_actual(), "reportes") else "asistencia"


app.add_template_filter(formatear_hora_12, "hora12")   # {{ r.hora_entrada|hora12 }} -> 08:05 AM


@app.context_processor
def datos_comunes():
    """Variables disponibles en todas las plantillas."""
    return {
        "usuario": usuario_actual(),
        "es_admin": es_administrador(usuario_actual()),
        "puede": lambda permiso: tiene_permiso(usuario_actual(), permiso),
        "csrf_token": session.get("csrf", ""),
    }


@app.before_request
def proteger():
    session.setdefault("csrf", secrets.token_hex(16))
    # CSRF: todo POST debe traer el token de la sesion
    if request.method == "POST":
        enviado = request.form.get("csrf", "")
        if not hmac.compare_digest(session["csrf"], enviado):
            abort(400)
    # Login: sin sesion solo se ven las paginas publicas
    if request.endpoint in RUTAS_PUBLICAS or request.endpoint == "static":
        return None
    if usuario_actual() is None:
        if not any(u.get("rol") == ROL_ADMIN for u in cargar_usuarios()):
            return redirect(url_for("configuracion_inicial"))
        return redirect(url_for("login"))
    return None


@app.after_request
def cabeceras_seguridad(respuesta):
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    respuesta.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    return respuesta


def _iniciar_sesion(usuario):
    """Abre la sesion de 'usuario' con un token CSRF nuevo (evita fijacion de sesion)."""
    session.clear()
    session["csrf"] = secrets.token_hex(16)
    session["usuario"] = {"usuario": usuario["usuario"], "nombre": usuario["nombre"], "rol": usuario["rol"],
                          "codigo_empleado": usuario.get("codigo_empleado", "")}
    session.permanent = True


def _segundos_bloqueo(usuario):
    cantidad, ultimo = intentos_fallidos.get(usuario, (0, 0))
    if cantidad >= MAX_INTENTOS:
        restante = SEGUNDOS_BLOQUEO - (time.time() - ultimo)
        if restante > 0:
            return int(restante) + 1
        intentos_fallidos.pop(usuario, None)
    return 0


# ------------------------------------------------------------------ login / logout
@app.route("/configuracion-inicial", methods=["GET", "POST"])
def configuracion_inicial():
    """Primera vez: crea el Administrador de la empresa; el SuperAdmin técnico es interno."""
    lista = cargar_usuarios()
    if any(u.get("rol") == ROL_ADMIN for u in lista):
        return redirect(url_for("login"))
    if request.method == "POST":
        f = request.form
        if f.get("clave", "") != f.get("clave2", ""):
            flash("Las contraseñas no coinciden.", "error")
        else:
            ok, mensaje = crear_usuario(lista, f.get("usuario", ""), f.get("nombre", ""),
                                        ROL_ADMIN, f.get("clave", ""))
            if ok and insertar_usuario(lista[-1]):
                _iniciar_sesion(lista[-1])
                auditar("Insertar", "Usuario", f"Administrador inicial {lista[-1]['usuario']}")
                flash(mensaje, "ok")
                return redirect(url_for("inicio"))
            flash(mensaje if not ok else "No se pudo guardar el usuario.", "error")
    return render_template("login.html", modo="setup")


@app.route("/login", methods=["GET", "POST"])
def login():
    if usuario_actual() is not None:
        return redirect(url_for("inicio"))
    if request.method == "POST":
        nombre_original = request.form.get("usuario", "")
        nombre = nombre_original.strip().lower()
        clave = request.form.get("clave", "")
        # Validacion del servidor: HTML/JS son solo ayudas y no se confian.
        # Rechaza entradas enormes antes de ejecutar el hash costoso PBKDF2.
        if not (4 <= len(nombre_original) <= 15) or len(clave) > 128 or not clave:
            flash("Usuario o contraseña incorrectos.", "error")
            return render_template("login.html", modo="login",
                                   hay_admin=any(u.get("rol") == ROL_ADMIN for u in cargar_usuarios()))
        espera = _segundos_bloqueo(nombre)
        if espera:
            flash(f"Demasiados intentos. Espere {espera} segundos.", "error")
        else:
            # El formulario de login solo recibe usuario y clave. El rol y los permisos
            # siempre se obtienen de la cuenta almacenada, nunca de datos del navegador.
            encontrado = autenticar_con_rol(cargar_usuarios(), nombre, clave, None)
            if encontrado:
                intentos_fallidos.pop(nombre, None)
                _iniciar_sesion(encontrado)
                auditar("Login", "Sesion", "Inicio de sesion (web)")
                return redirect(url_for("inicio"))
            cantidad = intentos_fallidos.get(nombre, (0, 0))[0] + 1
            intentos_fallidos[nombre] = (cantidad, time.time())
            registrar_auditoria(nombre[:20] or "(vacio)", "Login fallido", "Sesion", "Credenciales o rol incorrectos (web)")
            flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html", modo="login",
                                   hay_admin=any(u.get("rol") == ROL_ADMIN for u in cargar_usuarios()))


@app.post("/logout")
def logout():
    auditar("Logout", "Sesion", "Cierre de sesion (web)")
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------ rutas
@app.route("/")
def inicio():
    vista = request.args.get("vista") or vista_inicial()
    ahora = datetime.now()

    if vista not in PERMISO_POR_VISTA:           # direccion inventada: se vuelve al inicio del rol
        return redirect(url_for("inicio", vista=vista_inicial()))
    if not tiene_permiso(usuario_actual(), PERMISO_POR_VISTA[vista]):
        flash(MENSAJE_SIN_PERMISO, "error")
        return redirect(url_for("inicio", vista=vista_inicial()))

    # --- Trabajadores (con busqueda binaria opcional)
    lista_emp = empleados
    buscar = request.args.get("buscar", "").strip().upper()
    if buscar and tiene_permiso(usuario_actual(), "trabajadores"):
        encontrado = buscar_binario_recursivo(ordenar_empleados_por_codigo(empleados), buscar)
        lista_emp = [encontrado] if encontrado else []
        auditar("Buscar", "Trabajador", f"Codigo {buscar[:10]}: " + ("encontrado" if encontrado else "no encontrado"))
        if not encontrado:
            flash("Trabajador no encontrado.", "error")

    # --- Edicion de un trabajador (solo Administrador)
    emp_editar = None
    if vista == "editar":
        emp_editar = buscar_empleado_por_codigo(empleados, request.args.get("codigo", ""))
        if emp_editar is None or emp_editar["estado"] != "Activo":
            flash("Ese trabajador no existe o esta dado de baja.", "error")
            return redirect(url_for("inicio", vista="trabajadores"))

    # --- Asistencias (filtro por codigo / orden por fecha)
    # El Administrador ve todo; el Trabajador SOLO su propia asistencia (aunque cambie la direccion)
    usuario = usuario_actual()
    solo_propias = not es_administrador(usuario)
    codigo = request.args.get("codigo", "").strip().upper() if vista != "editar" else ""
    if solo_propias:
        codigo = codigo_propio(usuario) or "SIN-VINCULO"
    lista_asis = asistencias
    if codigo:
        lista_asis = buscar_asistencias_por_codigo(asistencias, codigo)
    if request.args.get("orden") == "fecha":
        lista_asis = ordenar_asistencias_por_fecha(lista_asis)
    tardanzas = contar_tardanzas_recursivo(lista_asis if codigo else asistencias)

    # --- Inicio del Administrador: resumen, ultimas asistencias y exportaciones
    hoy_txt, mes_actual = ahora.strftime("%Y-%m-%d"), ahora.strftime("%Y-%m")
    panel = {}
    if vista == "panel":
        panel = {
            "trabajadores": sum(1 for e in empleados if e.get("estado", "Activo") == "Activo"),
            "hoy": sum(1 for a in asistencias if a["fecha"] == hoy_txt),
            "abiertas": sum(1 for a in asistencias if a["hora_salida"] == ""),
            "tardanzas_mes": sum(1 for a in asistencias if a["fecha"].startswith(mes_actual) and a["tardanza"] == "Si"),
            "recientes": sorted(asistencias, key=lambda r: (r["fecha"], r["hora_entrada"]), reverse=True)[:8],
            "mes": mes_actual,
        }
    # --- Inicio del Trabajador: estado de SU jornada de hoy
    mi_estado = ""
    if solo_propias and codigo_propio(usuario):
        hoy_mias = [r for r in asistencias if r["codigo_empleado"] == codigo_propio(usuario) and r["fecha"] == hoy_txt]
        if not hoy_mias:
            mi_estado = "Hoy todavia no has marcado tu entrada."
        elif hoy_mias[-1]["hora_salida"] == "":
            mi_estado = f"Hoy entraste a las {formatear_hora_12(hoy_mias[-1]['hora_entrada'])}. Falta marcar tu salida."
        else:
            r = hoy_mias[-1]
            mi_estado = (f"Jornada de hoy completa: {formatear_hora_12(r['hora_entrada'])} a "
                         f"{formatear_hora_12(r['hora_salida'])} ({r['horas_trabajadas']} h).")
    elif solo_propias:
        mi_estado = "Tu usuario no esta vinculado a un trabajador."

    # --- Planilla
    mes = request.args.get("mes", ahora.strftime("%Y-%m")).strip()
    planilla, total, avisos = [], 0, []
    if vista == "planilla":
        if validar_formato_mes(mes):
            planilla = generar_planilla_mensual(empleados, asistencias, mes)
            total = total_planilla(planilla)
            for p in planilla:
                if p["horas_trabajadas"] == 0:
                    _, abiertas = contar_jornadas_mes(asistencias, p["codigo"], mes)
                    if abiertas:
                        avisos.append(f"{p['codigo']}: {abiertas} jornada(s) sin hora de salida")
        else:
            flash("Mes inválido. Usa el formato AAAA-MM (ej: 2026-09).", "error")

    # --- Auditoria y usuarios (solo Administrador)
    historial = listar_auditoria(200) if vista == "auditoria" else []
    lista_usuarios = (
        [{k: v for k, v in u.items() if k != "clave_hash"}
         for u in cargar_usuarios() if u.get("rol") != ROL_SUPERADMIN_INTERNO]
        if vista == "usuarios" else []
    )

    return render_template(
        "index.html", vista=vista, empleados=lista_emp, asistencias=lista_asis,
        cargos=CARGOS_VALIDOS, turnos=TURNOS_VALIDOS, tardanzas=tardanzas,
        hoy=ahora.strftime("%Y-%m-%d"), hora=ahora.strftime("%H:%M"),
        hora_h=ahora.strftime("%I"), hora_m=ahora.strftime("%M"), hora_ap="AM" if ahora.hour < 12 else "PM",
        turno_auto=turno_segun_hora(ahora.strftime("%H:%M")),
        corte_tarde=HORA_TOPE_POR_TURNO["Tarde"],
        mes=mes, planilla=planilla, total=total, avisos=avisos, buscar=buscar, codigo=codigo,
        emp_editar=emp_editar, historial=historial, lista_usuarios=lista_usuarios, roles=ROLES_VALIDOS,
        solo_propias=solo_propias, mi_codigo=codigo_propio(usuario) or "", panel=panel, mi_estado=mi_estado,
    )


@app.post("/trabajadores")
@requiere_permiso("trabajadores")
def ruta_registrar():
    f = request.form
    ok, mensaje = registrar_empleado(
        empleados, f.get("codigo", ""), f.get("nombres", ""), f.get("apellidos", ""),
        f.get("dni", ""), f.get("cargo", ""), f.get("turno", ""), f.get("tarifa", ""),
    )
    if ok:
        guardar_empleados(empleados)
        auditar("Insertar", "Trabajador", mensaje)
    flash(mensaje, "ok" if ok else "error")
    return redirect(url_for("inicio", vista="trabajadores"))


@app.post("/trabajadores/<codigo>/modificar")
@requiere_permiso("trabajadores")
def ruta_modificar(codigo):
    f = request.form
    ok, mensaje = modificar_empleado(
        empleados, codigo, f.get("nombres", ""), f.get("apellidos", ""),
        f.get("dni", ""), f.get("cargo", ""), f.get("turno", ""), f.get("tarifa", ""),
    )
    if ok and "sin cambios" not in mensaje:
        guardar_empleados(empleados)
        auditar("Modificar", "Trabajador", mensaje)
    flash(mensaje, "ok" if ok else "error")
    if not ok:
        return redirect(url_for("inicio", vista="editar", codigo=codigo))
    return redirect(url_for("inicio", vista="trabajadores"))


@app.post("/trabajadores/<codigo>/eliminar")
@requiere_permiso("trabajadores")
def ruta_eliminar(codigo):
    ok, mensaje = eliminar_empleado(empleados, asistencias, codigo)
    if ok:
        guardar_empleados(empleados)
        auditar("Eliminar", "Trabajador", mensaje)
    flash(mensaje, "ok" if ok else "error")
    return redirect(url_for("inicio", vista="trabajadores"))


def _codigo_para_asistencia(formulario):
    """
    El Administrador elige el trabajador; el Trabajador SOLO puede marcar la suya.
    Retorna (codigo, None) o (None, mensaje_de_error).
    """
    usuario = usuario_actual()
    enviado = formulario.get("codigo", "")
    if es_administrador(usuario):
        return enviado, None
    propio = codigo_propio(usuario)
    if propio is None:
        return None, "Tu usuario no esta vinculado a un trabajador. Pidele al Administrador que lo vincule."
    if enviado.strip() and not puede_ver_codigo(usuario, enviado):
        auditar("Acceso denegado", "Asistencia", f"Intento de marcar la asistencia de {enviado.strip().upper()[:10]}")
        return None, "Solo puedes registrar tu propia asistencia."
    return propio, None


def _hora_del_formulario(formulario):
    """
    La pantalla envia la hora en tres casillas (hora 1-12, minutos y AM/PM). Se acepta tambien un
    campo unico 'hora' (HH:MM o h:MM AM/PM). Retorna el texto de la hora tal como se recibio.
    """
    unica = formulario.get("hora", "").strip()
    if unica:
        return unica
    return f"{formulario.get('hora_h', '').strip()}:{formulario.get('hora_m', '').strip()} {formulario.get('hora_ap', '').strip()}"


def _validar_marcacion(formulario):
    """
    Reglas de la pantalla de asistencia que valen para ENTRADA y SALIDA.
    Retorna (fecha, hora_24h, turno, None) o (None, None, None, mensaje_de_error):
      - solo la fecha de hoy (nada de fechas pasadas ni futuras);
      - hora valida (12 h con AM/PM o 24 h);
      - un turno elegido (Manana o Tarde): sin turno no se marca.
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    if formulario.get("fecha", "").strip() != hoy:
        return None, None, None, (f"Solo se puede marcar con la fecha de hoy ({hoy}). "
                                  "No se admiten fechas pasadas ni futuras.")
    hora = normalizar_hora(_hora_del_formulario(formulario))
    if hora is None:
        return None, None, None, "Hora invalida. Elija la hora (1-12), los minutos y AM o PM."
    turno = normalizar_turno(formulario.get("turno", ""))
    if turno is None:
        return None, None, None, "Seleccione un turno (Mañana o Tarde) para marcar la entrada o la salida."
    return hoy, hora, turno, None


@app.post("/entrada")
@requiere_permiso("asistencia")
def ruta_entrada():
    f = request.form
    codigo, error = _codigo_para_asistencia(f)
    fecha = hora = turno = None
    if not error:
        fecha, hora, turno, error = _validar_marcacion(f)
    if error:
        flash(error, "error")
        return redirect(url_for("inicio", vista="asistencia"))
    ok, mensaje = marcar_entrada(asistencias, empleados, codigo, fecha, hora, turno)
    if ok:
        guardar_asistencias(asistencias)
        auditar("Insertar", "Asistencia", f"{mensaje} Fecha {fecha}.")
    flash(mensaje, "ok" if ok else "error")
    return redirect(url_for("inicio", vista="asistencia"))


@app.post("/salida")
@requiere_permiso("asistencia")
def ruta_salida():
    f = request.form
    codigo, error = _codigo_para_asistencia(f)
    fecha = hora = None
    if not error:
        fecha, hora, _turno, error = _validar_marcacion(f)
    if error:
        flash(error, "error")
        return redirect(url_for("inicio", vista="asistencia"))
    ok, mensaje = marcar_salida(asistencias, codigo, fecha, hora)
    if ok:
        guardar_asistencias(asistencias)
        auditar("Modificar", "Asistencia",
                f"Salida de {codigo.strip().upper()} el {fecha} a las {formatear_hora_12(hora)}.")
    flash(mensaje, "ok" if ok else "error")
    return redirect(url_for("inicio", vista="asistencia"))


@app.post("/usuarios")
@requiere_permiso("usuarios")
def ruta_crear_usuario():
    f = request.form
    if f.get("clave", "") != f.get("clave2", ""):
        flash("Las contraseñas no coinciden.", "error")
        return redirect(url_for("inicio", vista="usuarios"))
    lista = cargar_usuarios()
    ok, mensaje = crear_usuario(lista, f.get("usuario", ""), f.get("nombre", ""), f.get("rol", ""), f.get("clave", ""),
                                f.get("codigo_empleado", ""), empleados)
    if ok and not insertar_usuario(lista[-1]):
        ok, mensaje = False, "No se pudo guardar el usuario."
    if ok:
        auditar("Insertar", "Usuario", f"Usuario {lista[-1]['usuario']} ({lista[-1]['rol']})")
    flash(mensaje, "ok" if ok else "error")
    return redirect(url_for("inicio", vista="usuarios"))


@app.route("/exportar")
@requiere_permiso("reportes")
def ruta_exportar():
    """La planilla del mes se exporta unicamente a Excel (.xlsx)."""
    mes = request.args.get("mes", "").strip()
    formato = request.args.get("formato", "excel")
    if not validar_formato_mes(mes):
        flash("Mes inválido. Usa el formato AAAA-MM.", "error")
        return redirect(url_for("inicio", vista="planilla"))
    if formato != "excel":
        flash("Solo se puede exportar a Excel.", "error")
        return redirect(url_for("inicio", vista="planilla", mes=mes))
    planilla = generar_planilla_mensual(empleados, asistencias, mes)
    ruta = exportar_a_excel(empleados, asistencias, planilla=planilla)
    if not ruta:
        flash("No se pudo generar el archivo (¿está abierto en otro programa?).", "error")
        return redirect(url_for("inicio", vista="planilla", mes=mes))
    auditar("Exportar", "Reporte", f"Planilla {mes}: EXCEL (web)")
    return send_file(ruta, as_attachment=True, download_name=f"reporte_asistencia_{mes}.xlsx")
