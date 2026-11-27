# -*- coding: utf-8 -*-
"""
MODELO - Auditoria (historial de cambios).

Registra QUIEN hizo QUE y CUANDO: Insertar, Modificar, Eliminar, Buscar,
Exportar, Login, Logout y Login fallido. Los registros solo se agregan: la base
de datos impide modificarlos o borrarlos (ver models/base_datos.py).
Nunca se guardan contraseñas en el detalle.
"""

from datetime import datetime

from models import base_datos

ACCIONES = ("Acceso denegado", "Insertar", "Modificar", "Eliminar", "Buscar", "Exportar",
            "Login", "Logout", "Login fallido")
MAX_DETALLE = 500


def registrar_auditoria(usuario, accion, entidad, detalle="", ruta=None):
    """
    Guarda una linea del historial con la fecha y hora actuales.
    Retorna True si se guardo. 'ruta' permite usar otra base (pruebas).
    """
    if accion not in ACCIONES:
        raise ValueError(f"Accion de auditoria no permitida: {accion!r}")
    registro = {
        "usuario": usuario or "(sin sesion)",
        "accion": accion,
        "entidad": entidad,
        "detalle": str(detalle)[:MAX_DETALLE],
        "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return base_datos.insertar_auditoria(registro, ruta or base_datos.RUTA_BD)


def listar_auditoria(limite=200, ruta=None):
    """Ultimos registros del historial, del mas reciente al mas antiguo."""
    return base_datos.cargar_auditoria(limite, ruta or base_datos.RUTA_BD)
