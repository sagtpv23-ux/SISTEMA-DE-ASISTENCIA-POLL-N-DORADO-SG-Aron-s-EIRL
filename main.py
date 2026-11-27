"""Sistema de Asistencia de Trabajadores - SG Aron's EIRL (Pollon Dorado)
Punto de entrada de la version de CONSOLA.   Ejecutar:  python main.py
Arquitectura MVC:  models/ (datos y reglas)  views/ (lo que se ve)  controllers/ (interaccion)."""

import sys
from controllers.consola_controller import main

def configurar_utf8():
    """
    Fuerza UTF-8 en la entrada/salida estandar si estan redirigidas a un archivo
    o tuberia (donde Windows usaria cp1252 y fallaria con ciertos caracteres).
    En una terminal normal no se toca: Python ya la maneja en Unicode.
    """
    for flujo in (sys.stdin, sys.stdout, sys.stderr):
        try:
            if not flujo.isatty() and flujo.encoding.lower().replace("-", "") != "utf8":
                flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

if __name__ == "__main__":
    configurar_utf8()
    main()
