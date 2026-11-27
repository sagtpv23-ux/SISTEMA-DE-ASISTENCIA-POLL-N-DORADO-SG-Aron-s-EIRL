"""Casos de prueba automaticos del prototipo (arquitectura MVC) (solo libreria estandar + openpyxl).
Ejecutar:  python pruebas.py
Cada caso compara el resultado esperado con el obtenido y muestra OK / FALLO.
Con --json ruta.json guarda ademas los resultados (usado para el informe)."""

import builtins
import copy
import re
from datetime import datetime, timedelta
import contextlib
from contextlib import closing
import io
import json
import os
import sqlite3
import sys
import tempfile

from modelos.empleado import (
    registrar_empleado,
    ordenar_empleados_por_codigo,
    buscar_binario_recursivo,
)
from modelos.asistencia import (
    marcar_entrada,
    marcar_salida,
    calcular_horas_trabajadas,
    ordenar_asistencias_por_fecha,
    contar_tardanzas_recursivo,
    completar_turnos,
    HORA_TOPE_POR_TURNO,
    turno_segun_hora,
)
from modelos.planilla import generar_planilla_mensual, total_planilla, contar_jornadas_mes, meses_con_datos
from modelos.base_datos import (guardar_empleados, cargar_empleados, guardar_asistencias,
                               cargar_asistencias, importar_desde_csv)
from modelos.validaciones import (validar_formato_mes, validar_nombre, validar_formato_fecha,
                                 validar_dni, validar_tarifa_hora, normalizar_hora, formatear_hora_12)
from viwe.reporte_excel import exportar_a_excel
from modelos import base_datos
from vistas import consola as vista
from controladores import consola_controller

RESULTADOS = []

def caso(codigo, descripcion, esperado, funcion):
    """Ejecuta una prueba; funcion() retorna (obtenido_texto, cumple_bool)."""
    try:
        obtenido, ok = funcion()
    except Exception as error:  # una prueba nunca debe romper a las demas
        obtenido, ok = f"Excepcion: {error}", False
    RESULTADOS.append({"id": codigo, "descripcion": descripcion, "esperado": esperado,
                       "obtenido": obtenido, "ok": ok})
    print(f"[{'OK' if ok else 'FALLO'}] {codigo} {descripcion}")
    print(f"        esperado: {esperado}")
    print(f"        obtenido: {obtenido}")


def con_entradas(funcion, entradas):
    """Ejecuta funcion() simulando el teclado. Retorna (resultado, texto_impreso, entradas_usadas)."""
    cola = iter(entradas); usadas = [0]
    def teclado(prompt=""):
        usadas[0] += 1
        try:
            return next(cola)
        except StopIteration:
            raise EOFError
    original, salida = builtins.input, io.StringIO()
    builtins.input = teclado
    try:
        with contextlib.redirect_stdout(salida):
            resultado = funcion()
    finally:
        builtins.input = original
    return resultado, salida.getvalue(), usadas[0]


def base():
    """Estado limpio: 2 trabajadores (uno de cada turno habitual)."""
    empleados, asistencias = [], []
    registrar_empleado(empleados, "E001", "Carlos", "Ramirez", "71234567", "Parrillero", "M", "8.5")
    registrar_empleado(empleados, "E002", "Maria", "Lopez", "75647382", "Mesero", "T", "7.0")
    return empleados, asistencias


def ejecutar():
    # Las pruebas fijan los topes en 08:00 y 14:00 para comprobar la logica, de modo
    # que siguen pasando aunque se cambien las horas reales en modulo_asistencia.py.
    topes_reales = dict(HORA_TOPE_POR_TURNO)
    HORA_TOPE_POR_TURNO.update({"Mañana": "08:00", "Tarde": "14:00"})

    # ---------- Registro y validaciones de trabajadores ----------
    def p01():
        emp, _ = [], []
        ok, msg = registrar_empleado(emp, "E001", "Carlos", "Ramirez", "71234567", "Parrillero", "M", "8.5")
        return msg, ok and emp[0]["turno"] == "Mañana"
    caso("P01", "Registrar trabajador valido (turno M, tarifa 8.5)", "Registro exitoso, turno Mañana", p01)

    def p02():
        emp, _ = base()
        ok, msg = registrar_empleado(emp, "E001", "Otro", "Nombre", "70000000", "Caja", "T", "8")
        return msg, (not ok)
    caso("P02", "Codigo de trabajador duplicado", "Rechazado", p02)

    def p03():
        emp, _ = base()
        ok, msg = registrar_empleado(emp, "X1", "Ana", "Torres", "70234815", "Caja", "T", "8")
        return msg, (not ok)
    caso("P03", "Codigo con formato invalido (X1)", "Rechazado", p03)

    def p04():
        emp, _ = base()
        ok, msg = registrar_empleado(emp, "E003", "Luis", "Perez", "123", "Caja", "T", "8")
        return msg, (not ok)
    caso("P04", "DNI invalido (123)", "Rechazado", p04)

    def p05():
        emp, _ = base()
        ok, msg = registrar_empleado(emp, "E003", "Ana", "Torres", "70234815", "Caja", "Noche", "8")
        return msg, (not ok)
    caso("P05", "Turno inexistente (Noche): la empresa solo tiene 2 turnos", "Rechazado", p05)

    def p06():
        emp, _ = base()
        ok, msg = registrar_empleado(emp, "E003", "Ana", "Torres", "70234815", "Caja", "T", "-5")
        return msg, (not ok)
    caso("P06", "Tarifa por hora negativa (-5)", "Rechazado", p06)

    # ---------- Entrada, tardanza por turno y turno por jornada ----------
    def p07():
        emp, asi = base()
        ok, msg = marcar_entrada(asi, emp, "E001", "2026-09-01", "08:00")
        return f"{msg} tardanza={asi[0]['tardanza']}", ok and asi[0]["tardanza"] == "No"
    caso("P07", "Entrada turno Mañana a las 08:00 (puntual)", "Sin tardanza", p07)

    def p08():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-01", "08:15")
        return f"tardanza={asi[0]['tardanza']}", asi[0]["tardanza"] == "Si"
    caso("P08", "Entrada turno Mañana a las 08:15", "Tardanza", p08)

    def p09():
        emp, asi = base()
        marcar_entrada(asi, emp, "E002", "2026-09-01", "14:00")
        return f"turno={asi[0]['turno']} tardanza={asi[0]['tardanza']}", asi[0]["tardanza"] == "No"
    caso("P09", "Entrada turno Tarde a las 14:00 (antes marcaba tardanza por error)", "Sin tardanza", p09)

    def p10():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-01", "8:00")
        return f"hora guardada={asi[0]['hora_entrada']} tardanza={asi[0]['tardanza']}", (
            asi[0]["hora_entrada"] == "08:00" and asi[0]["tardanza"] == "No")
    caso("P10", "Hora escrita sin cero inicial (8:00)", "Se normaliza a 08:00, sin tardanza", p10)

    def p11():
        emp, asi = base()
        ok, msg = marcar_entrada(asi, emp, "E001", "2026-09-03", "14:00", "T")
        return f"turno de la jornada={asi[0]['turno']} (habitual: {emp[0]['turno']})", (
            ok and asi[0]["turno"] == "Tarde")
    caso("P11", "Trabajador de Mañana cubre el turno Tarde", "Jornada registrada como Tarde", p11)

    def p12():
        emp, asi = base()
        ok, msg = marcar_entrada(asi, emp, "E999", "2026-09-01", "08:00")
        return msg, (not ok)
    caso("P12", "Entrada de trabajador inexistente (E999)", "Rechazado", p12)

    def p13():
        emp, asi = base()
        ok, msg = marcar_entrada(asi, emp, "E001", "2026-13-45", "08:00")
        return msg, (not ok)
    caso("P13", "Fecha invalida (2026-13-45)", "Rechazado", p13)

    # ---------- Salida y horas ----------
    def p14():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-01", "08:00")
        ok, msg = marcar_salida(asi, "E001", "2026-09-01", "07:00")
        return msg, (not ok)
    caso("P14", "Hora de salida anterior a la de entrada", "Rechazado", p14)

    def p15():
        emp, asi = base()
        ok, msg = marcar_salida(asi, "E001", "2026-09-01", "17:00")
        return msg, (not ok)
    caso("P15", "Salida sin entrada abierta ese dia", "Rechazado", p15)

    def p16():
        horas = calcular_horas_trabajadas("08:00", "17:30")
        return f"{horas} h", horas == 9.5
    caso("P16", "Calculo de horas trabajadas 08:00 a 17:30", "9.5 h", p16)

    # ---------- Busqueda, ordenamiento y recursividad ----------
    def p17():
        emp, _ = base()
        ordenados = ordenar_empleados_por_codigo(emp)
        hallado = buscar_binario_recursivo(ordenados, "E002")
        no_hallado = buscar_binario_recursivo(ordenados, "E999")
        return f"E002 -> {hallado['nombres']}; E999 -> {no_hallado}", hallado is not None and no_hallado is None
    caso("P17", "Busqueda binaria recursiva por codigo (existente e inexistente)", "E002 hallado, E999 None", p17)

    def p18():
        emp = []
        for cod in ("E003", "E001", "E002"):
            registrar_empleado(emp, cod, "N", "A", "7023481" + cod[-1], "Caja", "M", "8")
        orden = [e["codigo"] for e in ordenar_empleados_por_codigo(emp)]
        return str(orden), orden == ["E001", "E002", "E003"]
    caso("P18", "Ordenamiento de trabajadores por codigo (sorted)", "['E001','E002','E003']", p18)

    def p19():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-03", "08:00"); marcar_salida(asi, "E001", "2026-09-03", "17:00")
        marcar_entrada(asi, emp, "E001", "2026-09-01", "08:00"); marcar_salida(asi, "E001", "2026-09-01", "17:00")
        marcar_entrada(asi, emp, "E002", "2026-09-02", "14:00"); marcar_salida(asi, "E002", "2026-09-02", "22:00")
        fechas = [r["fecha"] for r in ordenar_asistencias_por_fecha(asi)]
        return str(fechas), fechas == ["2026-09-01", "2026-09-02", "2026-09-03"]
    caso("P19", "Ordenamiento de asistencias por fecha (sorted)", "Fechas ascendentes", p19)

    def p20():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-01", "08:15")   # tardanza
        marcar_entrada(asi, emp, "E002", "2026-09-01", "14:30")   # tardanza
        marcar_entrada(asi, emp, "E001", "2026-09-02", "08:00")   # puntual
        total = contar_tardanzas_recursivo(asi)
        return f"{total} tardanzas", total == 2
    caso("P20", "Conteo recursivo de tardanzas (3 entradas, 2 tarde)", "2", p20)

    # ---------- Planilla mensual ----------
    def p21():
        emp, asi = base()
        for fecha, hi, hs, turno in (("2026-09-01", "08:00", "17:00", ""),
                                     ("2026-09-02", "08:00", "17:00", ""),
                                     ("2026-09-03", "14:00", "22:00", "T")):
            marcar_entrada(asi, emp, "E001", fecha, hi, turno)
            marcar_salida(asi, "E001", fecha, hs)
        plan = generar_planilla_mensual(emp, asi, "2026-09")
        c = plan[0]
        texto = (f"E001: Mañana {c['horas_manana']} h + Tarde {c['horas_tarde']} h = "
                 f"{c['horas_trabajadas']} h x S/ {c['tarifa_hora']} = S/ {c['pago_mensual']}")
        return texto, (c["horas_manana"] == 18.0 and c["horas_tarde"] == 8.0 and c["pago_mensual"] == 221.0)
    caso("P21", "Planilla mensual con horas separadas por turno", "18 h Mañana + 8 h Tarde = 26 h x 8.5 = S/ 221.00", p21)

    def p22():
        return (f"2026-09 -> {validar_formato_mes('2026-09')}; 'septiembre' -> {validar_formato_mes('septiembre')}",
                validar_formato_mes("2026-09") and not validar_formato_mes("septiembre"))
    caso("P22", "Validacion del mes de la planilla (AAAA-MM)", "2026-09 valido, 'septiembre' invalido", p22)

    # ---------- Archivos y excepciones ----------
    def p23():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-01", "08:00"); marcar_salida(asi, "E001", "2026-09-01", "17:00")
        plan = generar_planilla_mensual(emp, asi, "2026-09")
        with tempfile.TemporaryDirectory() as tmp:
            ruta = exportar_a_excel(emp, asi, os.path.join(tmp, "reporte.xlsx"), planilla=plan)
            from openpyxl import load_workbook
            hojas = load_workbook(ruta).sheetnames
        return f"hojas: {hojas}", hojas == ["Empleados", "Asistencias", "Planilla mensual"]
    caso("P23", "Exportar a Excel (.xlsx)", "3 hojas: Empleados, Asistencias, Planilla mensual", p23)

    def p24():
        emp, asi = base()
        with tempfile.TemporaryDirectory() as tmp:
            ruta = exportar_a_excel(emp, asi, os.path.join(tmp, "no_existe", "reporte.xlsx"))
        return f"retorno={ruta} (el programa no se cerro)", ruta is None
    caso("P24", "Excepcion controlada: no se puede guardar el Excel", "Mensaje de error y retorno None, sin cerrar el programa", p24)

    def p25():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-01", "08:00"); marcar_salida(asi, "E001", "2026-09-01", "17:00")
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "asistencia.db")
            guardar_empleados(emp, bd); guardar_asistencias(asi, bd)
            emp2, asi2 = cargar_empleados(bd), cargar_asistencias(bd)
        return (f"{len(emp2)} trabajadores y {len(asi2)} asistencia(s) recuperados; turno jornada={asi2[0]['turno']}",
                len(emp2) == 2 and len(asi2) == 1 and asi2[0]["turno"] == "Mañana")
    caso("P25", "Persistencia en SQLite: guardar y volver a cargar", "Los datos se recuperan completos", p25)

    # ---------- Correcciones: jornadas sin salida, archivos viejos y recursion larga ----------
    def p26():
        n = 5000
        lista = [{"tardanza": "Si" if i % 2 == 0 else "No"} for i in range(n)]
        total = contar_tardanzas_recursivo(lista)
        return f"{n} registros -> {total} tardanzas (sin RecursionError)", total == 2500
    caso("P26", "Conteo recursivo por mitades con 5000 registros", "2500, sin superar el limite de recursion", p26)

    def p27():
        emp, _ = base()
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "asistencias_viejas.csv")
            bd = os.path.join(tmp, "asistencia.db")
            with open(ruta, "w", encoding="utf-8", newline="") as f:  # version anterior: sin columna turno
                f.write("codigo_empleado,fecha,hora_entrada,hora_salida,horas_trabajadas,tardanza,observaciones\n")
                f.write("E002,2026-10-15,14:00,22:00,8.0,No,\n")
            importar_desde_csv(os.path.join(tmp, "no_hay.csv"), ruta, bd)  # CSV viejo -> SQLite
            asi = cargar_asistencias(bd)
        actualizados = completar_turnos(asi, emp)
        c = generar_planilla_mensual(emp, asi, "2026-10")[1]
        return (f"{actualizados} registro actualizado, turno={asi[0]['turno']}, "
                f"horas Tarde={c['horas_tarde']}, pago=S/ {c['pago_mensual']}",
                actualizados == 1 and asi[0]["turno"] == "Tarde" and c["pago_mensual"] == 56.0)
    caso("P27", "CSV de una version anterior sin columna turno: se importa a SQLite", "Se asigna el turno habitual y la planilla cuenta las horas", p27)

    def p28():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-10-15", "08:00")
        cerradas, abiertas = contar_jornadas_mes(asi, "E001", "2026-10")
        c = generar_planilla_mensual(emp, asi, "2026-10")[0]
        return f"cerradas={cerradas}, abiertas={abiertas}, horas={c['horas_trabajadas']}", (cerradas, abiertas) == (0, 1) and c["horas_trabajadas"] == 0
    caso("P28", "Jornada sin hora de salida: se detecta y la planilla queda en 0", "0 cerradas, 1 abierta, 0 horas", p28)

    def p29():
        emp, asi = base()
        for fecha in ("2026-10-02", "2026-09-30", "2026-10-15"):
            marcar_entrada(asi, emp, "E001", fecha, "08:00")
            marcar_salida(asi, "E001", fecha, "12:00")
        meses = meses_con_datos(asi)
        return str(meses), meses == ["2026-09", "2026-10"]
    caso("P29", "Meses con asistencias registradas (para detectar un mes equivocado)", "['2026-09', '2026-10']", p29)

    # ---------- Captura de datos: no se avanza con un dato invalido ----------
    guardados = (consola_controller.guardar_empleados, consola_controller.guardar_asistencias)
    consola_controller.guardar_empleados = lambda *a, **k: True      # las pruebas no escriben en data/
    consola_controller.guardar_asistencias = lambda *a, **k: True
    # La auditoria tampoco escribe en data/: se captura en una lista (usuario, accion, entidad, detalle)
    AUDITORIA = []
    registrar_original = consola_controller.registrar_auditoria
    consola_controller.registrar_auditoria = (
        lambda usuario, accion, entidad, detalle="", ruta=None: AUDITORIA.append((usuario, accion, entidad, detalle)) or True)

    def p30():
        buenos = ["Ana María", "O'Brien", "Pérez-Ñandú", "Luis"]
        malos = ["Ana@", "Ana3", "", "@", "Ana  ", "12"]
        ok = all(validar_nombre(x) for x in buenos[:3] + ["Luis"]) and not any(validar_nombre(x) for x in malos[:4] + ["12"])
        return f"validos={[validar_nombre(x) for x in buenos]}, invalidos={[validar_nombre(x) for x in malos[:4]]}", ok
    caso("P30", "Nombres: letras, tildes y espacios si; @, numeros y vacio no", "Acepta Ana María, O'Brien, Pérez-Ñandú; rechaza Ana@, Ana3, vacio y @", p30)

    def p31():
        r = [validar_formato_fecha("2026-9-1"), validar_formato_fecha("2026-02-30"), validar_formato_fecha("2026-09-01"),
             validar_dni("1234567²"), validar_dni("7123456a"), validar_dni("71234567")]
        return str(r), r == [False, False, True, False, False, True]
    caso("P31", "Fecha y DNI estrictos (2026-9-1, 30 de febrero, DNI con letras o simbolos)", "[False, False, True, False, False, True]", p31)

    def p32():
        emp = []
        entradas = ["X1", "E001",
                    "@", "Ana3", "", "Ana",
                    "Pérez@", "Pérez Ñ",
                    "123", "1234567a", "71234567",
                    "Gerente", "caja",
                    "N", "m",
                    "abc", "-3", "0", "8.5"]
        _, texto, usadas = con_entradas(lambda: consola_controller.opcion_registrar(emp), entradas)
        rechazos = texto.count("Dato invalido")
        e = emp[0] if emp else {}
        ok = (len(emp) == 1 and e["nombres"] == "Ana" and e["apellidos"] == "Pérez Ñ" and e["cargo"] == "Caja"
              and e["turno"] == "Mañana" and e["tarifa_hora"] == 8.5 and rechazos == 12 and usadas == len(entradas))
        return f"{rechazos} datos rechazados, {usadas} entradas usadas; registrado: {e.get('codigo')} {e.get('nombres')} {e.get('apellidos')}", ok
    caso("P32", "Registro por consola: repite cada pregunta hasta recibir un dato valido", "12 rechazos y 1 trabajador registrado con los datos validos", p32)

    def p33():
        emp, _ = base()
        res, texto, usadas = con_entradas(lambda: vista.pedir_dato("Codigo:", consola_controller.regla_codigo_nuevo(emp)), ["E001", "e002", "X1", "E003"])
        return f"devuelve {res} tras {usadas} intentos ({texto.count('Dato invalido')} rechazados)", res == "E003" and usadas == 4
    caso("P33", "Codigo nuevo: rechaza el formato incorrecto y los codigos ya registrados", "Devuelve E003 tras 4 intentos", p33)

    def p34():
        emp = []
        _, texto, usadas = con_entradas(lambda: consola_controller.opcion_registrar(emp), ["E001", "@", "cancelar"])
        return f"{len(emp)} trabajadores guardados, {usadas} entradas usadas", emp == [] and "cancelada" in texto and usadas == 3
    caso("P34", "Escribir cancelar sale de la operacion sin guardar nada", "0 trabajadores registrados", p34)

    def p35():
        emp, asi = base()
        entradas = ["E999", "E001", "2026-9-1", "2026-02-30", "2026-09-01", "25:00", "8:00", "X", ""]
        # el Administrador elige el trabajador; el Trabajador solo marca el suyo
        consola_controller.SESION["usuario"] = {"usuario": "admin", "nombre": "Admin", "rol": "Administrador", "codigo_empleado": ""}
        _, texto, usadas = con_entradas(lambda: consola_controller.opcion_entrada(emp, asi), entradas)
        consola_controller.SESION["usuario"] = None
        r = asi[0] if asi else {}
        ok = (len(asi) == 1 and r["fecha"] == "2026-09-01" and r["hora_entrada"] == "08:00" and r["turno"] == "Mañana"
              and texto.count("Dato invalido") == 5 and usadas == len(entradas))
        return f"{texto.count('Dato invalido')} datos rechazados; jornada: {r.get('fecha')} {r.get('hora_entrada')} {r.get('turno')}", ok
    caso("P35", "Marcar entrada por consola: exige trabajador existente, fecha real, hora valida y turno valido", "5 rechazos y la jornada 2026-09-01 08:00 Mañana", p35)

    def p36():
        nombres_ok = ["José Ñandú", "María Peña", "Núñez-Müller", "O'Brien", "Çelik", "Zoë"]
        nombres_mal = ["Ana3", "Ana@", "", "   ", "_x"]
        acepta = all(validar_nombre(n) for n in nombres_ok)
        rechaza = not any(validar_nombre(n) for n in nombres_mal)
        emp = []
        registrar_empleado(emp, "E001", "José Ñandú", "Peña Núñez", "71234567", "Cocina", "M", "9")
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "asistencia.db")
            guardar_empleados(emp, bd)
            releido = cargar_empleados(bd)
            with closing(sqlite3.connect(bd)) as con:
                codificacion = con.execute("PRAGMA encoding").fetchone()[0]
            sin_bom, con_bom = os.path.join(tmp, "sin_bom.csv"), os.path.join(tmp, "con_bom.csv")
            contenido = "codigo,nombres,apellidos\nE009,Ángela,Muñoz\n"
            with open(sin_bom, "wb") as f:
                f.write(contenido.encode("utf-8"))  # CSV UTF-8 antiguo, sin BOM
            with open(con_bom, "wb") as f:
                f.write(contenido.encode("utf-8-sig"))  # CSV guardado desde Excel, con BOM
            bd2 = os.path.join(tmp, "otra.db")
            importar_desde_csv(sin_bom, os.path.join(tmp, "x.csv"), bd2)
            sin = cargar_empleados(bd2)
            bd3 = os.path.join(tmp, "tercera.db")
            importar_desde_csv(con_bom, os.path.join(tmp, "x.csv"), bd3)
            con = cargar_empleados(bd3)
        ok = (acepta and rechaza and codificacion == "UTF-8"
              and releido[0]["nombres"] == "José Ñandú" and releido[0]["apellidos"] == "Peña Núñez"
              and (sin[0]["nombres"], sin[0]["apellidos"]) == ("Ángela", "Muñoz")
              and (con[0]["nombres"], con[0]["apellidos"]) == ("Ángela", "Muñoz"))
        return (f"SQLite {codificacion}: {releido[0]['nombres']} {releido[0]['apellidos']}; "
                f"CSV sin BOM: {sin[0]['nombres']}; CSV con BOM: {con[0]['nombres']}"), ok
    caso("P36", "Caracteres especiales (tildes, ñ, ü, ç) en UTF-8: validacion, SQLite e importacion de CSV", "Se aceptan, se guardan y se leen sin deformarse", p36)

    def p37():
        emp, _ = base()
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "asistencia.db")
            guardar_empleados(emp, bd)
            repetido = [dict(emp[0]), dict(emp[0])]  # mismo codigo dos veces: la base lo rechaza
            with contextlib.redirect_stdout(io.StringIO()):
                resultado = guardar_empleados(repetido, bd)
            despues = cargar_empleados(bd)
            guardar_empleados(emp[:1], bd)
            menos = cargar_empleados(bd)
        return (f"guardado invalido -> {resultado}; siguen {len(despues)} trabajadores; "
                f"tras guardar 1, quedan {len(menos)}"), (resultado is False and len(despues) == len(emp) and len(menos) == 1)
    caso("P37", "SQLite: la transaccion se deshace si un guardado falla (codigo repetido)", "Retorna False y los datos anteriores quedan intactos", p37)

    def p38():
        import ast
        raiz = os.path.dirname(os.path.abspath(__file__))
        def importa(carpeta):
            modulos = set()
            for nombre in sorted(os.listdir(os.path.join(raiz, carpeta))):
                if nombre.endswith(".py"):
                    arbol = ast.parse(open(os.path.join(raiz, carpeta, nombre), encoding="utf-8").read())
                    for nodo in ast.walk(arbol):
                        if isinstance(nodo, ast.ImportFrom) and nodo.module:
                            modulos.add(nodo.module.split(".")[0])
                        elif isinstance(nodo, ast.Import):
                            modulos.update(a.name.split(".")[0] for a in nodo.names)
            return modulos
        modelos, vistas = importa("models"), importa("views")
        ok = (not modelos & {"views", "controllers", "flask"}) and ("controllers" not in vistas)
        return (f"models importa {sorted(modelos & {'views', 'controllers', 'flask'}) or 'nada de views/controllers/flask'}; "
                f"views importa controllers: {'controllers' in vistas}"), ok
    caso("P38", "Arquitectura MVC: los modelos no dependen de vistas ni controladores, y las vistas no dependen de controladores",
         "models no importa views, controllers ni flask; views no importa controllers", p38)

    def p39():
        malas = ["inf", "infinity", "-inf", "nan", "1e999", "1e2", "999999999", "501", "0", "-5", "8.555", "8,5", "٣", "", "abc"]
        buenas = ["1", "8", "8.5", "10.30", "500"]
        rechaza = [t for t in malas if validar_tarifa_hora(t)]
        acepta = [t for t in buenas if not validar_tarifa_hora(t)]
        emp = []
        ok_reg, _ = registrar_empleado(emp, "E001", "Ana", "Perez", "70234815", "Caja", "M", "infinity")
        return (f"{len(malas)} tarifas invalidas rechazadas (inf, nan, 1e999, 501...); "
                f"{len(buenas)} validas aceptadas; 'infinity' al registrar -> {ok_reg}"), (not rechaza and not acepta and ok_reg is False and emp == [])
    caso("P39", "Limites de la tarifa: infinito, nan, notacion cientifica, mas de 500, mas de 2 decimales y digitos no ASCII",
         "Rechazadas; solo 0 < tarifa <= 500 con maximo 2 decimales", p39)

    def p40():
        emp = []
        registrar_empleado(emp, "E001", "Ana", "Perez", "70234815", "Caja", "M", "8.5")
        resultados = []
        def intentar(entrada, salida):
            asi = []
            ok_e, _ = marcar_entrada(asi, emp, "E001", "2026-09-01", entrada)
            if not ok_e:
                return "entrada rechazada"
            ok_s, _ = marcar_salida(asi, "E001", "2026-09-01", salida)
            return "aceptada" if ok_s else "salida rechazada"
        casos = [("23:59", "23:59", "entrada rechazada"), ("05:59", "08:00", "entrada rechazada"),
                 ("08:00", "08:00", "salida rechazada"), ("08:00", "23:59", "salida rechazada"),
                 ("08:00", "21:00", "salida rechazada"), ("08:00", "17:00", "aceptada"), ("22:59", "23:00", "aceptada")]
        fallos = [(e, s_, esp, intentar(e, s_)) for e, s_, esp in casos if intentar(e, s_) != esp]
        return (f"{len(casos)} combinaciones de horas comprobadas (23:59-23:59, 08:00-08:00, 08:00-23:59, 08:00-21:00 de 13 h...); "
                f"fallos: {len(fallos)}"), not fallos
    caso("P40", "Horario y duracion: entrada fuera del horario (23:59), salida igual a la entrada, salida a las 23:59 y jornada de mas de 12 horas",
         "Rechazadas; solo se aceptan marcaciones entre 06:00 y 23:00 y jornadas de hasta 12 h", p40)

    def p43():
        invalidos = ["00000000", "11111111", "99999999", "12345678", "87654321", "01234567", "98765432",
                     "12121212", "12341234", "1234567", "123456789", "1234567a", "٣٣٣٣٣٣٣٣", "7123 4567", ""]
        validos = ["71234567", "60562175", "45789623", "00000001", "04567890", "70234815"]
        mal_aceptados = [d for d in invalidos if validar_dni(d)]
        mal_rechazados = [d for d in validos if not validar_dni(d)]
        emp = []
        r1 = registrar_empleado(emp, "E001", "Ana", "Perez", "00000000", "Caja", "M", "8")[0]
        r2 = registrar_empleado(emp, "E001", "Ana", "Perez", "71234567", "Caja", "M", "8")[0]
        r3, msg3 = registrar_empleado(emp, "E002", "Luis", "Rojas", "71234567", "Caja", "M", "8")
        return (f"{len(invalidos)} DNI invalidos rechazados (00000000, 11111111, 12345678, 12121212...); "
                f"{len(validos)} validos aceptados; DNI repetido entre trabajadores -> {r3}"), \
               (not mal_aceptados and not mal_rechazados and r1 is False and r2 is True and r3 is False and len(emp) == 1)
    caso("P43", "DNI no valido: todos iguales (00000000), secuencias (12345678), patrones repetidos, letras y DNI repetido entre trabajadores",
         "Rechazados; solo 8 digitos con aspecto real y sin repetirse en otro trabajador", p43)

    PAYLOADS_SQL = ["'; DROP TABLE empleados; --", "' OR '1'='1", "E001' OR '1'='1", "Robert'); DROP TABLE asistencias;--",
                    "1; DELETE FROM empleados", "\" OR \"\"=\"", "admin'--", "x' UNION SELECT * FROM empleados --"]

    def p41():
        import tempfile
        validos = dict(codigo="E001", nombres="Ana", apellidos="Perez", dni="70234815", cargo="Caja", turno="M", tarifa="8.5")
        intentos = aceptados = 0
        for payload in PAYLOADS_SQL:
            for campo in validos:
                datos = dict(validos); datos[campo] = payload
                emp = []
                intentos += 1
                if registrar_empleado(emp, datos["codigo"], datos["nombres"], datos["apellidos"], datos["dni"],
                                      datos["cargo"], datos["turno"], datos["tarifa"])[0]:
                    aceptados += 1
            emp = []
            registrar_empleado(emp, "E001", "Ana", "Perez", "70234815", "Caja", "M", "8.5")
            asi = []
            intentos += 4
            aceptados += sum([marcar_entrada(asi, emp, payload, "2026-09-01", "08:00")[0], marcar_salida(asi, payload, "2026-09-01", "17:00")[0],
                              validar_formato_fecha(payload), validar_formato_mes(payload)])
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "asistencia.db")
            emp = []; registrar_empleado(emp, "E001", "Ana", "Perez", "70234815", "Caja", "M", "8.5")
            guardar_empleados(emp, bd); guardar_asistencias([], bd)
            with closing(sqlite3.connect(bd)) as con:
                tablas = sorted(r[0] for r in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"))
            quedan = len(cargar_empleados(bd))
        return (f"{intentos} intentos de inyeccion SQL en formularios, {aceptados} aceptados; "
                f"tablas {tablas} intactas con {quedan} trabajador"), (aceptados == 0 and tablas == ["asistencias", "auditoria", "empleados", "usuarios"] and quedan == 1)
    caso("P41", "Inyeccion SQL en los campos del programa (codigo, nombres, DNI, cargo, turno, tarifa, fecha, mes)",
         "Todos los intentos son rechazados por la validacion y las tablas siguen intactas", p41)

    def p42():
        import tempfile
        maliciosa = [{"codigo": "E001", "nombres": "'; DROP TABLE empleados; --", "apellidos": "' OR '1'='1", "dni": "70234815",
                      "cargo": "Caja", "turno": "Tarde", "tarifa_hora": "8.5", "estado": "Activo"}]
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "asistencia.db")
            guardado = guardar_empleados(maliciosa, bd)       # aunque la validacion fallara, la consulta es parametrizada
            leidos = cargar_empleados(bd)
            with closing(sqlite3.connect(bd)) as con:
                tablas = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
            literal = leidos == [{k: str(v) for k, v in maliciosa[0].items()}]
            bloqueada = False
            try:
                base_datos._guardar(bd, "empleados; DROP TABLE empleados", base_datos.CAMPOS_EMPLEADOS, [])
            except ValueError:
                bloqueada = True
        intactas = {"asistencias", "empleados"} <= tablas
        return (f"texto malicioso guardado como dato literal: {literal}; tablas intactas: {intactas}; "
                f"nombre de tabla no permitido bloqueado: {bloqueada}"), (guardado and literal and intactas and bloqueada)
    caso("P42", "Inyeccion SQL a nivel de base de datos: consultas parametrizadas y lista blanca de tablas",
         "El texto malicioso se guarda como dato literal sin ejecutarse y un nombre de tabla no permitido es bloqueado", p42)


    # ================= Autenticacion, roles, auditoria y CRUD =================
    import copy
    import re
    import shutil
    import zipfile
    from models import usuarios as mod_usuarios, auditoria as mod_auditoria
    from models.empleado import modificar_empleado, eliminar_empleado
    from views.reporte_csv import exportar_a_csv
    from views.reporte_json import exportar_a_json

    def usuarios_base():
        lista = []
        mod_usuarios.crear_usuario(lista, "admin", "Ana Admin", "Administrador", "Clave1234")
        mod_usuarios.crear_usuario(lista, "trabajador1", "Omar Trabajador", "Trabajador", "Clave5678", "E001")
        return lista
    USUARIOS_BASE = usuarios_base()          # se calcula una sola vez (PBKDF2 es lento a proposito)

    def con_claves(funcion, entradas, claves):
        """Como con_entradas, pero tambien simula las contraseñas que se escriben ocultas (getpass)."""
        cola = iter(claves)
        original = vista.getpass.getpass
        def falso(prompt=""):
            try:
                return next(cola)
            except StopIteration:
                raise EOFError
        vista.getpass.getpass = falso
        try:
            return con_entradas(funcion, entradas)
        finally:
            vista.getpass.getpass = original

    def como(usuario):
        """Fija la sesion de consola (None = sin sesion)."""
        consola_controller.SESION["usuario"] = (
            None if usuario is None else {"usuario": usuario, "nombre": usuario.title(),
                                           "rol": "Administrador" if usuario == "admin" else "Trabajador",
                                           "codigo_empleado": "" if usuario == "admin" else "E001"})

    def p44():
        h1, h2 = (mod_usuarios.hashear_contrasena("Clave1234") for _ in range(2))
        partes = h1.split("$")
        verif = mod_usuarios.verificar_contrasena
        malas = ["abc1", "sololetrasss", "12345678"]
        rechaza = [c for c in malas if mod_usuarios.validar_contrasena(c) is None]
        ok = ("Clave1234" not in h1 and h1 != h2 and partes[0] == "pbkdf2_sha256" and int(partes[1]) >= 100000
              and verif("Clave1234", h1) and not verif("clave1234", h1) and not verif("x", "basura")
              and mod_usuarios.validar_contrasena("Clave1234") is None
              and mod_usuarios.validar_contrasena("admin123", "admin123") is not None and not rechaza)
        return (f"hash {partes[0]} con {partes[1]} iteraciones, texto plano ausente, dos hashes distintos para la misma clave; "
                f"contraseñas debiles aceptadas: {rechaza or 'ninguna'}"), ok
    caso("P44", "Contraseñas: hash PBKDF2 con sal (nunca texto plano) y politica minima",
         "Hash distinto cada vez, verificacion correcta, claves cortas/sin numero/igual al usuario rechazadas", p44)

    def p45():
        lista = copy.deepcopy(USUARIOS_BASE)
        bien = mod_usuarios.autenticar(lista, "ADMIN", "Clave1234")
        mal_clave = mod_usuarios.autenticar(lista, "admin", "Clave12345")
        no_existe = mod_usuarios.autenticar(lista, "nadie", "Clave1234")
        inyeccion = mod_usuarios.autenticar(lista, "' OR '1'='1", "' OR '1'='1")
        ok_crear, _ = mod_usuarios.crear_usuario(lista, "ADMIN", "Otro Nombre", "Trabajador", "Clave1234")
        mal_rol, _ = mod_usuarios.crear_usuario(lista, "nuevo", "Otro Nombre", "Jefe", "Clave1234")
        return (f"correcta -> {bien and bien['usuario']}; clave mala -> {mal_clave}; usuario inexistente -> {no_existe}; "
                f"inyeccion -> {inyeccion}; usuario repetido -> {ok_crear}; rol inventado -> {mal_rol}"), (
            bien is not None and "clave_hash" not in bien and bien["rol"] == "Administrador"
            and mal_clave is None and no_existe is None and inyeccion is None and not ok_crear and not mal_rol)
    caso("P45", "Autenticacion: solo entra con usuario y contraseña correctos (sin revelar el hash)",
         "Credenciales correctas entran; incorrectas, inexistentes e inyeccion SQL no", p45)

    def p46():
        lista = copy.deepcopy(USUARIOS_BASE)
        AUDITORIA.clear(); como(None)
        entro, _, _ = con_claves(lambda: consola_controller.iniciar_sesion(lista), ["A", "ADMIN"], ["Clave1234"])
        sesion_ok = consola_controller.SESION["usuario"]["usuario"] if consola_controller.SESION["usuario"] else None
        como(None); AUDITORIA.clear()
        fallo, texto, _ = con_claves(lambda: consola_controller.iniciar_sesion(lista), ["A", "admin"] * 3, ["a1", "b2", "c3"])
        fallos = [a for a in AUDITORIA if a[1] == "Login fallido"]
        como(None)
        return (f"entro={entro and entro['usuario']}, sesion={sesion_ok}; 3 claves malas -> {fallo}, "
                f"login fallidos auditados: {len(fallos)}"), (
            entro is not None and sesion_ok == "admin" and fallo is None and len(fallos) == 3
            and "Demasiados" in texto and consola_controller.SESION["usuario"] is None)
    caso("P46", "Login de consola: 3 intentos y se cierra; cada fallo queda en la auditoria",
         "Entra con clave correcta; con 3 claves malas no entra y registra 3 'Login fallido'", p46)

    def p47():
        lista = []
        como(None); AUDITORIA.clear()
        guardado = consola_controller.insertar_usuario
        consola_controller.insertar_usuario = lambda u: True
        try:
            res, texto, _ = con_claves(lambda: consola_controller.iniciar_sesion(lista),
                                       ["admin", "Ana Perez"], ["Clave1234", "otraClave9", "Clave1234", "Clave1234"])
        finally:
            consola_controller.insertar_usuario = guardado
        como(None)
        return (f"sin usuarios previos -> se crea administrador: {res and res['usuario']}, rol {res and res['rol']}; "
                f"clave guardada como hash: {lista[0]['clave_hash'].startswith('pbkdf2_sha256$')}; "
                f"clave que no coincide se repite: {'no coinciden' in texto}"), (
            res is not None and res["rol"] == "Administrador" and len(lista) == 1
            and "Clave1234" not in lista[0]["clave_hash"] and "no coinciden" in texto
            and any(a[1] == "Insertar" and a[2] == "Usuario" for a in AUDITORIA))
    caso("P47", "Primera ejecucion: no hay usuario ni contraseña por defecto, se crea el Administrador",
         "Lista vacia -> pide crear administrador (clave confirmada y guardada con hash)", p47)

    def p48():
        emp, _ = base()
        ok1, m1 = modificar_empleado(emp, "e001", "Carlos", "Ramirez", "71234567", "Mesero", "T", "9")
        ok2, m2 = modificar_empleado(emp, "E001", "Carlos", "Ramirez", "75647382", "Mesero", "T", "9")   # DNI de E002
        ok3, m3 = modificar_empleado(emp, "E001", "Carlos", "Ramirez", "71234567", "Chef", "T", "9")
        ok4, m4 = modificar_empleado(emp, "E099", "A", "B", "71234567", "Caja", "M", "8")
        ok5, m5 = modificar_empleado(emp, "E001", "Carlos", "Ramirez", "71234567", "Mesero", "T", "9")    # igual: sin cambios
        e1 = emp[0]
        return (f"cambio valido -> {ok1} ({e1['cargo']}, {e1['turno']}, S/ {e1['tarifa_hora']}); DNI de otro -> {ok2}; "
                f"cargo invalido -> {ok3}; codigo inexistente -> {ok4}; sin cambios -> {m5}"), (
            ok1 and e1["cargo"] == "Mesero" and e1["turno"] == "Tarde" and e1["tarifa_hora"] == 9.0
            and "cargo" in m1 and not ok2 and not ok3 and not ok4 and ok5 and "sin cambios" in m5
            and e1["dni"] == "71234567")
    caso("P48", "Modificar trabajador: aplica las mismas validaciones y no permite el DNI de otro",
         "Cambios validos se guardan; DNI repetido, cargo invalido o codigo inexistente se rechazan", p48)

    def p49():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-01", "08:00")
        marcar_salida(asi, "E001", "2026-09-01", "16:00")
        ok_baja, m_baja = eliminar_empleado(emp, asi, "E001")        # tiene historial -> baja
        ok_borra, m_borra = eliminar_empleado(emp, asi, "E002")      # sin historial -> se borra
        ok_otra, _ = eliminar_empleado(emp, asi, "E001")             # ya esta de baja
        ok_no, _ = eliminar_empleado(emp, asi, "E077")
        nueva, _ = [], []
        entra, _msg = marcar_entrada(asi, emp, "E001", "2026-09-02", "08:00")
        mod_ok, _ = modificar_empleado(emp, "E001", "Carlos", "Ramirez", "71234567", "Caja", "M", "8")
        plan = generar_planilla_mensual(emp, asi, "2026-09")
        return (f"con historial -> baja ({emp[0]['estado']}), asistencias conservadas: {len(asi)}; sin historial -> borrado "
                f"(quedan {len(emp)}); ya de baja -> {ok_otra}; inactivo marca entrada -> {entra}; "
                f"inactivo en planilla: {len(plan)} filas"), (
            ok_baja and emp[0]["estado"] == "Inactivo" and len(asi) == 1 and ok_borra and len(emp) == 1
            and not ok_otra and not ok_no and not entra and not mod_ok and plan == [])
    caso("P49", "Eliminar trabajador: baja si tiene historial, borrado si no; un inactivo no marca ni cobra",
         "Historial conservado, inactivo fuera de la planilla y sin poder marcar entrada", p49)

    def p50():
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "a.db")
            for accion in ("Insertar", "Modificar", "Eliminar", "Buscar"):
                mod_auditoria.registrar_auditoria("admin", accion, "Trabajador", f"{accion} E001", ruta=bd)
            filas = mod_auditoria.listar_auditoria(10, ruta=bd)
            bloqueos = 0
            with closing(sqlite3.connect(bd)) as con:
                for sentencia in ("UPDATE auditoria SET usuario = 'otro'", "DELETE FROM auditoria"):
                    try:
                        con.execute(sentencia)
                    except sqlite3.DatabaseError:
                        bloqueos += 1
                restantes = con.execute("select count(*) from auditoria").fetchone()[0]
            invalida = False
            try:
                mod_auditoria.registrar_auditoria("admin", "Hackear", "x", ruta=bd)
            except ValueError:
                invalida = True
        formato = all(re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", f["fecha_hora"]) for f in filas)
        orden = [f["accion"] for f in filas]
        return (f"{len(filas)} registros, orden {orden}, fecha y hora validas: {formato}; "
                f"UPDATE/DELETE bloqueados: {bloqueos}/2 (quedan {restantes}); accion inventada rechazada: {invalida}"), (
            orden == ["Buscar", "Eliminar", "Modificar", "Insertar"] and formato and bloqueos == 2
            and restantes == 4 and invalida and all(f["usuario"] == "admin" for f in filas))
    caso("P50", "Auditoria: guarda usuario, accion y fecha/hora, y no se puede editar ni borrar",
         "4 acciones registradas (mas reciente primero); UPDATE y DELETE directos bloqueados por la base", p50)

    def p51():
        emp, asi = [], []
        como("admin"); AUDITORIA.clear()
        con_entradas(lambda: consola_controller.opcion_registrar(emp),
                     ["E001", "Ana", "Perez", "70234815", "Caja", "M", "8.5"])
        con_entradas(lambda: consola_controller.opcion_buscar(emp), ["E001"])
        con_entradas(lambda: consola_controller.opcion_modificar(emp), ["E001", "", "", "", "Mesero", "", "9"])
        cancelar, _, _ = con_entradas(lambda: consola_controller.opcion_eliminar(emp, asi), ["E001", "NO"]), 0, 0
        antes = len(AUDITORIA)
        con_entradas(lambda: consola_controller.opcion_eliminar(emp, asi), ["E001", "SI"])
        como(None)
        acciones = [(a[0], a[1], a[2]) for a in AUDITORIA]
        esperado = [("admin", "Insertar", "Trabajador"), ("admin", "Buscar", "Trabajador"),
                    ("admin", "Modificar", "Trabajador"), ("admin", "Eliminar", "Trabajador")]
        return (f"{len(acciones)} movimientos: {[a[1] for a in acciones]}; 'NO' no elimina ni audita: {antes == 3}; "
                f"trabajador quedo: {len(emp)}"), (acciones == esperado and antes == 3 and emp == [])
    caso("P51", "La consola audita Insertar, Buscar, Modificar y Eliminar con el usuario de la sesion",
         "4 movimientos a nombre de 'admin'; responder NO a eliminar no deja rastro", p51)

    def p52():
        lista = copy.deepcopy(USUARIOS_BASE)
        originales = (consola_controller.cargar_usuarios, consola_controller.cargar_empleados,
                      consola_controller.cargar_asistencias, consola_controller.listar_auditoria)
        consola_controller.cargar_usuarios = lambda: lista
        consola_controller.cargar_empleados = lambda *a, **k: []
        consola_controller.cargar_asistencias = lambda *a, **k: []
        consola_controller.listar_auditoria = lambda *a, **k: [
            {"fecha_hora": "2026-01-01 10:00:00", "usuario": "admin", "accion": "Insertar", "entidad": "Trabajador", "detalle": "x"}]
        try:
            # El Trabajador prueba TODAS las opciones de administracion (1,2,3,9,10,11,12,13,14) y luego una permitida (4)
            _, texto_tr, _ = con_claves(consola_controller.main,
                                        ["T", "trabajador1", "1", "2", "3", "9", "10", "11", "12", "13", "14", "4", "cancelar", "0"],
                                        ["Clave5678"])
            como(None)
            _, texto_ad, _ = con_claves(consola_controller.main, ["A", "admin", "13", "0"], ["Clave1234"])
            como(None)
        finally:
            (consola_controller.cargar_usuarios, consola_controller.cargar_empleados,
             consola_controller.cargar_asistencias, consola_controller.listar_auditoria) = originales
        denegadas = texto_tr.count("No tienes permiso.")
        menu_tr = texto_tr.split("Elige una opcion")[0]
        return (f"Trabajador: {denegadas}/9 opciones de administrador con 'No tienes permiso.'; su menu no muestra "
                f"administracion: {'Registrar trabajador' not in menu_tr and 'Solo Administrador' not in menu_tr}; "
                f"opcion 4 (marcar entrada) si entra: {'Operacion cancelada' in texto_tr}; "
                f"Administrador ve la auditoria: {'Fecha y hora' in texto_ad}"), (
            denegadas == 9 and "Registrar trabajador" not in menu_tr and "Solo Administrador" not in menu_tr
            and "4. Marcar entrada" in menu_tr and "Operacion cancelada" in texto_tr
            and "Fecha y hora" in texto_ad and "Solo Administrador" in texto_ad)
    caso("P52", "Roles en consola: el Trabajador solo ve y registra asistencia; lo demas muestra 'No tienes permiso.'",
         "Opciones 1,2,3,9,10,11,12,13,14 denegadas al Trabajador; la opcion 4 funciona; el Administrador si ve la auditoria", p52)

    def p53():
        emp, asi = base()
        marcar_entrada(asi, emp, "E001", "2026-09-01", "08:00"); marcar_salida(asi, "E001", "2026-09-01", "16:00")
        emp[0]["nombres"] = "José"
        plan = generar_planilla_mensual(emp, asi, "2026-09")
        with tempfile.TemporaryDirectory() as tmp:
            rutas = exportar_a_csv(emp, asi, planilla=plan, carpeta=tmp, mes="2026-09")
            nombres = [os.path.basename(r) for r in rutas]
            csv_emp = open(rutas[0], encoding="utf-8-sig").read()
            ruta_json = exportar_a_json(emp, asi, planilla=plan, nombre_archivo=os.path.join(tmp, "r.json"), mes="2026-09")
            datos = json.load(open(ruta_json, encoding="utf-8"))
            crudo = open(ruta_json, encoding="utf-8").read()
            falla = exportar_a_json(emp, asi, nombre_archivo=os.path.join(tmp, "no_existe", "r.json"))
        ok = (nombres == ["empleados.csv", "asistencias.csv", "planilla_2026-09.csv"] and "José" in csv_emp
              and csv_emp.splitlines()[0].startswith("codigo,nombres") and set(datos) >= {"empleados", "asistencias", "planilla"}
              and datos["planilla"][0]["pago_mensual"] == 68.0 and "José" in crudo and falla is None)
        return (f"CSV: {nombres}; JSON con {len(datos['empleados'])} empleados, {len(datos['asistencias'])} asistencia, "
                f"planilla S/ {datos['planilla'][0]['pago_mensual']}; tildes UTF-8 intactas; ruta invalida -> {falla}"), ok
    caso("P53", "Exportacion a archivos de texto: CSV (3 archivos) y JSON, en UTF-8",
         "Archivos creados con los datos correctos y las tildes bien; una ruta invalida no cierra el programa", p53)

    # ---------- Interfaz web (cliente de pruebas de Flask, sin abrir navegador ni tocar data/) ----------
    ESTADO_WEB = {}

    def cargar_web():
        if "web" not in ESTADO_WEB:
            guardados_bd = (base_datos.cargar_empleados, base_datos.cargar_asistencias, base_datos.CARPETA_DATA)
            carpeta = tempfile.mkdtemp()
            base_datos.cargar_empleados = lambda *a, **k: []
            base_datos.cargar_asistencias = lambda *a, **k: []
            base_datos.CARPETA_DATA = carpeta                 # la clave secreta se crea en una carpeta temporal
            try:
                from controllers import web_controller
            finally:
                base_datos.cargar_empleados, base_datos.cargar_asistencias, base_datos.CARPETA_DATA = guardados_bd
                shutil.rmtree(carpeta, ignore_errors=True)
            ESTADO_WEB["web"] = web_controller
        return ESTADO_WEB["web"]

    HOY = datetime.now().strftime("%Y-%m-%d")      # la web solo admite marcar con la fecha de hoy
    MES_HOY = HOY[:7]

    def web_nuevo(usuarios=None):
        web = cargar_web()
        lista = copy.deepcopy(USUARIOS_BASE) if usuarios is None else usuarios
        aud = []
        web.cargar_usuarios = lambda: lista
        web.insertar_usuario = lambda u: True
        web.registrar_auditoria = (lambda usuario, accion, entidad, detalle="", ruta=None:
                                   aud.append((usuario, accion, entidad, detalle)) or True)
        web.listar_auditoria = lambda limite=200, ruta=None: [
            {"fecha_hora": "2026-01-01 10:00:00", "usuario": u, "accion": a, "entidad": e, "detalle": d}
            for (u, a, e, d) in reversed(aud)]
        web.guardar_empleados = lambda *a, **k: True
        web.guardar_asistencias = lambda *a, **k: True
        web.empleados, web.asistencias = [], []
        web.intentos_fallidos.clear()
        web.app.config["TESTING"] = True
        return web, web.app.test_client(), lista, aud

    def csrf(cliente):
        with cliente.session_transaction() as sesion:
            return sesion.get("csrf", "")

    def entrar(cliente, usuario, clave):
        cliente.get("/login")
        return cliente.post("/login", data={"usuario": usuario, "clave": clave, "csrf": csrf(cliente)})

    def p54():
        web, c, lista, aud = web_nuevo()
        sin_sesion = c.get("/")
        sin_token = c.post("/login", data={"usuario": "admin", "clave": "Clave1234"})
        mala = entrar(c, "admin", "Clave0000")
        buena = entrar(c, "admin", "Clave1234")
        con_sesion = c.get("/")
        c.post("/logout", data={"csrf": csrf(c)})
        tras_logout = c.get("/")
        # bloqueo tras 5 intentos fallidos
        web2, c2, _, _ = web_nuevo()
        for _ in range(5):
            entrar(c2, "trabajador1", "mala0000")
        bloqueado = entrar(c2, "trabajador1", "Clave5678")
        # primera vez: sin usuarios se pide crear el administrador
        web3, c3, lista3, _ = web_nuevo(usuarios=[])
        a_setup = c3.get("/")
        c3.get("/configuracion-inicial")
        distintas = c3.post("/configuracion-inicial", data={"usuario": "jefe", "nombre": "Jefe Nuevo", "clave": "Clave1234",
                                                           "clave2": "Otra12345", "csrf": csrf(c3)})
        creado = c3.post("/configuracion-inicial", data={"usuario": "jefe", "nombre": "Jefe Nuevo", "clave": "Clave1234",
                                                        "clave2": "Clave1234", "csrf": csrf(c3)})
        pagina = c3.get("/")
        ok = (sin_sesion.status_code == 302 and "/login" in sin_sesion.location and sin_token.status_code == 400
              and mala.status_code == 200 and "incorrectos" in mala.get_data(as_text=True)
              and buena.status_code == 302 and con_sesion.status_code == 200
              and tras_logout.status_code == 302 and "Demasiados intentos" in bloqueado.get_data(as_text=True)
              and a_setup.status_code == 302 and "configuracion-inicial" in a_setup.location
              and len(lista3) == 1 and lista3[0]["rol"] == "Administrador" and creado.status_code == 302
              and pagina.status_code == 200)
        return (f"sin sesion -> {sin_sesion.status_code} a /login; POST sin token CSRF -> {sin_token.status_code}; "
                f"clave mala -> mensaje; clave buena -> {buena.status_code}; tras logout -> {tras_logout.status_code}; "
                f"5 fallos -> bloqueo; primera vez -> pide crear administrador"), ok
    caso("P54", "Web: hay que iniciar sesion, los formularios exigen token CSRF y 5 fallos bloquean al usuario",
         "Paginas protegidas, CSRF rechazado (400), bloqueo temporal y creacion del primer administrador", p54)

    def p55():
        web, c, lista, aud = web_nuevo()
        entrar(c, "trabajador1", "Clave5678")
        t = csrf(c)
        web.empleados.append({"codigo": "E001", "nombres": "Ana", "apellidos": "Perez", "dni": "70234815",
                              "cargo": "Caja", "turno": "Mañana", "tarifa_hora": 8.5, "estado": "Activo"})
        exportado = []
        web.exportar_a_excel = lambda *a, **k: exportado.append(1)     # si se llamara, el permiso fallo
        inicio = c.get("/").get_data(as_text=True)
        sin_permiso = 0
        for url in ("/?vista=trabajadores", "/?vista=editar&codigo=E001", "/?vista=planilla",
                    "/?vista=auditoria", "/?vista=usuarios", "/exportar?mes=2026-09&formato=excel",
                    "/?vista=asistencia&buscar=E001"):
            pagina = c.get(url, follow_redirects=True).get_data(as_text=True)
            if "No tienes permiso." in pagina:
                sin_permiso += 1
        # (la ultima direccion es de asistencia: no da error, pero tampoco ejecuta la busqueda de trabajadores)
        posts = (("/trabajadores", {"codigo": "E009", "nombres": "Luis", "apellidos": "Diaz", "dni": "46321987",
                                    "cargo": "Caja", "turno": "Mañana", "tarifa": "8"}),
                 ("/trabajadores/E001/modificar", {"nombres": "X", "apellidos": "Y", "dni": "70234815",
                                                   "cargo": "Caja", "turno": "Mañana", "tarifa": "9"}),
                 ("/trabajadores/E001/eliminar", {}),
                 ("/usuarios", {"usuario": "hackeo1", "nombre": "H", "rol": "Administrador",
                                "clave": "Clave1234", "clave2": "Clave1234"}))
        for url, datos in posts:
            datos["csrf"] = t
            if "No tienes permiso." in c.post(url, data=datos, follow_redirects=True).get_data(as_text=True):
                sin_permiso += 1
        intacto = (len(web.empleados) == 1 and web.empleados[0]["nombres"] == "Ana"
                   and web.empleados[0]["estado"] == "Activo" and len(lista) == 2)
        # Lo que SI puede hacer: registrar asistencia
        c.post("/entrada", data={"csrf": t, "codigo": "E001", "fecha": HOY, "hora": "08:00", "turno": "Mañana"})
        c.post("/salida", data={"csrf": t, "codigo": "E001", "fecha": HOY, "hora": "16:00", "turno": "Mañana"})
        registro_ok = len(web.asistencias) == 1 and web.asistencias[0]["hora_salida"] == "16:00"
        pestanas = [n for n in ("Trabajadores</a>", "Planilla mensual</a>", "Auditoría</a>", "Usuarios</a>") if n in inicio]
        buscar_filtrado = not any(a[1] == "Buscar" for a in aud)
        c.post("/logout", data={"csrf": t})

        entrar(c, "admin", "Clave1234")
        aud.append(("admin", "Insertar", "Trabajador", "<script>alert(1)</script>"))
        pagina_ad = c.get("/?vista=trabajadores").get_data(as_text=True)
        audit_ad = c.get("/?vista=auditoria").get_data(as_text=True)
        ok = (sin_permiso == 10 and intacto and not exportado and registro_ok and not pestanas
              and "Asistencia</a>" in inicio and "Marcar mi asistencia" in inicio and buscar_filtrado
              and ">Eliminar<" in pagina_ad and "Auditoría</a>" in pagina_ad and "Usuarios</a>" in pagina_ad
              and "Fecha y hora" in audit_ad and "&lt;script&gt;" in audit_ad and "<script>alert(1)" not in audit_ad)
        return (f"Trabajador: {sin_permiso}/10 intentos de entrar a trabajadores, planilla, auditoria, usuarios, exportar, "
                f"modificar, eliminar o crear usuario muestran 'No tienes permiso.'; datos intactos: {intacto}; "
                f"pestanas de administracion visibles: {pestanas or 'ninguna'}; si registra entrada y salida: {registro_ok}; "
                f"Administrador ve todo; el HTML de la auditoria se escapa (sin XSS)"), ok
    caso("P55", "Web: el Trabajador solo ve y registra asistencia; lo demas muestra 'No tienes permiso.'",
         "Rutas de administrador (ver y modificar) denegadas al Trabajador sin cambiar datos; pestañas ocultas; el HTML se escapa", p55)

    def p56():
        web, c, lista, aud = web_nuevo()
        entrar(c, "admin", "Clave1234")
        t = csrf(c)
        with tempfile.TemporaryDirectory() as tmp:
            web.exportar_a_excel = lambda e, a, planilla=None: exportar_a_excel(e, a, os.path.join(tmp, "r.xlsx"), planilla=planilla)
            c.post("/trabajadores", data={"csrf": t, "codigo": "E001", "nombres": "Ana", "apellidos": "Perez",
                                          "dni": "70234815", "cargo": "Caja", "turno": "Mañana", "tarifa": "8.5"})
            c.get("/?vista=trabajadores&buscar=E001")
            c.post("/entrada", data={"csrf": t, "codigo": "E001", "fecha": HOY, "hora_h": "08", "hora_m": "00", "hora_ap": "AM", "turno": "Mañana"})
            c.post("/salida", data={"csrf": t, "codigo": "E001", "fecha": HOY, "hora_h": "04", "hora_m": "00", "hora_ap": "PM", "turno": "Mañana"})
            c.post("/trabajadores/E001/modificar", data={"csrf": t, "nombres": "Ana", "apellidos": "Perez",
                   "dni": "70234815", "cargo": "Mesero", "turno": "Mañana", "tarifa": "9"})
            editar = c.get("/?vista=editar&codigo=E001")
            plan = generar_planilla_mensual(web.empleados, web.asistencias, MES_HOY)
            xlsx = c.get(f"/exportar?mes={MES_HOY}&formato=excel")
            js = c.get(f"/exportar?mes={MES_HOY}&formato=json")      # ya no existe: solo Excel
            zp = c.get(f"/exportar?mes={MES_HOY}&formato=csv")       # ya no existe: solo Excel
            malo = c.get(f"/exportar?mes={MES_HOY}&formato=exe")
            c.post("/trabajadores/E001/eliminar", data={"csrf": t})
            sin_token = c.post("/trabajadores/E001/eliminar", data={})
            nuevo_usuario = c.post("/usuarios", data={"csrf": t, "usuario": "trabajador2", "nombre": "Pedro Gomez", "rol": "Administrador",
                                                      "clave": "Clave2468", "clave2": "Clave2468"})
        acciones = [(a[0], a[1], a[2]) for a in aud]
        esperado = {("admin", "Insertar", "Trabajador"), ("admin", "Buscar", "Trabajador"), ("admin", "Insertar", "Asistencia"),
                    ("admin", "Modificar", "Asistencia"), ("admin", "Modificar", "Trabajador"), ("admin", "Exportar", "Reporte"),
                    ("admin", "Eliminar", "Trabajador"), ("admin", "Insertar", "Usuario")}
        ok = (esperado <= set(acciones) and "Ana" in editar.get_data(as_text=True) and xlsx.status_code == 200
              and plan[0]["pago_mensual"] == 72.0 and js.status_code == 302 and zp.status_code == 302
              and malo.status_code == 302 and sin_token.status_code == 400 and web.empleados[0]["estado"] == "Inactivo"
              and len(lista) == 3 and "Clave2468" not in str(aud))
        return (f"{len(acciones)} movimientos auditados a nombre de admin ({sorted({a[1] for a in acciones})}); "
                f"Excel 200 (planilla de 72.0), CSV/JSON/formato falso rechazados (solo Excel); "
                f"eliminar con historial -> {web.empleados[0]['estado']}; contraseñas fuera de la auditoria"), ok
    caso("P56", "Web: registrar, buscar, asistencia, modificar, eliminar, exportar (Excel) y crear usuario quedan auditados",
         "Cada accion deja su fila en la auditoria y la exportacion a Excel funciona", p56)


    # ---------- Reglas del nombre de usuario y roles (Administrador / Trabajador) ----------
    from models.usuarios import tiene_permiso, PERMISOS_POR_ROL
    from controllers.consola_controller import opciones_permitidas

    def p57():
        validos = ["Juan", "ana_2026", "A1b2", "abcdefghijklmno", "Usuario_01", "Zeta"]
        invalidos = {"abc": "entre 4 y 15", "abcdefghijklmnop": "entre 4 y 15", "1abc": "empezar con una letra",
                     "_abcd": "empezar con una letra", "12345": "empezar con una letra", "ab cd": "espacios",
                     " abcd": "espacios", "abcd ": "espacios", "ab\tcd": "espacios", "abcd\n": "espacios",
                     "ab-cd": "solo se permiten", "ab.cd": "solo se permiten", "a@bcd": "solo se permiten",
                     "ñandu1": "solo se permiten", "": "vacio"}
        mal_aceptados = [u for u in validos if mod_usuarios.error_usuario(u) is not None]
        mal_mensaje = [u for u, clave in invalidos.items() if clave not in (mod_usuarios.error_usuario(u) or "")]
        lista = []
        rechazados = [u for u in invalidos if mod_usuarios.crear_usuario(lista, u, "Ana Perez", "Trabajador", "Clave1234")[0]]
        creados = [mod_usuarios.crear_usuario(lista, u, "Ana Perez", "Trabajador", "Clave1234")[0] for u in ("Juan_01", "ana_2026")]
        repetido = mod_usuarios.crear_usuario(lista, "JUAN_01", "Otro Nombre", "Trabajador", "Clave1234")[0]
        return (f"{len(validos)} validos aceptados (letras, numeros y _; de 4 a 15; empiezan con letra); "
                f"{len(invalidos)} invalidos rechazados con su motivo (largo, primera letra, espacios, simbolos, vacio); "
                f"se guarda en minusculas: {lista[0]['usuario']}; 'JUAN_01' repetido -> {repetido}"), (
            not mal_aceptados and not mal_mensaje and not rechazados and all(creados) and not repetido
            and lista[0]["usuario"] == "juan_01" and len(lista) == 2)
    caso("P57", "Nombre de usuario: letras, numeros y _; empieza con letra; 4 a 15 caracteres; sin espacios ni simbolos",
         "Los invalidos se rechazan con un mensaje claro y no se crean; los validos se aceptan", p57)

    def p58():
        # consola: la pregunta se repite hasta que el usuario es valido (no deja continuar)
        lista = copy.deepcopy(USUARIOS_BASE)
        como("admin"); AUDITORIA.clear()
        guardado = consola_controller.insertar_usuario
        consola_controller.insertar_usuario = lambda u: True
        try:
            _, texto, usadas = con_claves(lambda: consola_controller.opcion_crear_usuario(lista),
                                          ["12345", "ab", "juan perez", "juan-perez", " Juan_01", "Juan_01",
                                           "Juan Perez", "X", "T"], ["Clave1234", "Clave1234"])
        finally:
            consola_controller.insertar_usuario = guardado
        como(None)
        rechazos = texto.count("Dato invalido")
        nuevo = next((u for u in lista if u["usuario"] == "juan_01"), None)
        # web: crear usuario y primera configuracion rechazan nombres invalidos
        web, c, lista_w, _ = web_nuevo()
        entrar(c, "admin", "Clave1234")
        mensajes = []
        for malo in ("12345", "ab", "juan perez", "juan-perez", "1juan"):
            r = c.post("/usuarios", data={"csrf": csrf(c), "usuario": malo, "nombre": "Juan Perez", "rol": "Trabajador",
                                          "clave": "Clave1234", "clave2": "Clave1234"}, follow_redirects=True)
            mensajes.append("Usuario invalido" in r.get_data(as_text=True))
        sin_crear = len(lista_w) == 2
        web2, c2, lista2, _ = web_nuevo(usuarios=[])
        c2.get("/configuracion-inicial")
        c2.post("/configuracion-inicial", data={"usuario": "9jefe", "nombre": "Jefe Nuevo", "clave": "Clave1234",
                                               "clave2": "Clave1234", "csrf": csrf(c2)})
        setup_rechazado = len(lista2) == 0
        return (f"consola: {rechazos} datos invalidos rechazados y repetidos hasta escribir uno correcto "
                f"(creado: {nuevo and nuevo['usuario']}, rol {nuevo and nuevo['rol']}); "
                f"web: 5/5 nombres invalidos con mensaje y sin crear usuario: {all(mensajes) and sin_crear}; "
                f"primer administrador con nombre invalido no se crea: {setup_rechazado}"), (
            rechazos == 6 and nuevo is not None and nuevo["rol"] == "Trabajador" and all(mensajes) and sin_crear
            and setup_rechazado)
    caso("P58", "Crear usuario: la consola repite la pregunta y la web muestra el error; no se puede continuar con un nombre invalido",
         "5 nombres invalidos y 1 rol invalido rechazados en consola; 5 en la web y 1 en la configuracion inicial", p58)

    def p59():
        admin = {"usuario": "a", "rol": "Administrador"}
        trab = {"usuario": "t", "rol": "Trabajador"}
        todos = {"asistencia", "trabajadores", "reportes", "auditoria", "usuarios"}
        ok_admin = all(tiene_permiso(admin, p) for p in todos)
        ok_trab = [p for p in sorted(todos) if tiene_permiso(trab, p)]
        raros = (tiene_permiso(None, "asistencia"), tiene_permiso({"rol": "Jefe"}, "asistencia"),
                 tiene_permiso(trab, "inventado"))
        como("admin"); op_admin = opciones_permitidas()
        como("trabajador1"); op_trab = opciones_permitidas()
        como(None)
        _, menu_tr, _ = con_entradas(lambda: vista.mostrar_menu({"usuario": "t", "rol": "Trabajador"}, op_trab), [])
        _, menu_ad, _ = con_entradas(lambda: vista.mostrar_menu({"usuario": "a", "rol": "Administrador"}, op_admin), [])
        return (f"Administrador: todos los permisos ({ok_admin}); Trabajador: {ok_trab}; rol o permiso desconocido -> {raros}; "
                f"opciones del Trabajador: {sorted(op_trab, key=int)}; el Administrador usa las {len(op_admin)}"), (
            ok_admin and ok_trab == ["asistencia"] and raros == (False, False, False)
            and op_trab == {"4", "5", "6", "7", "8"} and len(op_admin) == 14
            and "4. Marcar entrada" in menu_tr and "Eliminar" not in menu_tr and "Crear usuario" not in menu_tr
            and "Eliminar trabajador" in menu_ad and set(PERMISOS_POR_ROL) == {"Administrador", "Trabajador", "SuperAdmin"})
    caso("P59", "Tabla de permisos: Administrador todo; Trabajador solo asistencia; roles desconocidos sin permisos",
         "El Trabajador solo tiene 'asistencia' (opciones 4 a 8) y su menu no muestra la administracion", p59)

    def p60():
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "v.db")
            base_datos.insertar_usuario({"usuario": "vieja01", "nombre": "Ana", "rol": "Operador",
                                         "clave_hash": "x", "creado": "2026-01-01"}, bd)
            roles = [u["rol"] for u in base_datos.cargar_usuarios(bd)]
        return f"usuario creado con el rol anterior 'Operador' -> al abrir la base queda como {roles}", roles == ["Trabajador"]
    caso("P60", "Compatibilidad: los usuarios con el rol anterior 'Operador' pasan a 'Trabajador' al abrir la base",
         "Rol 'Trabajador'", p60)

    def empleados_prueba():
        emp = []
        registrar_empleado(emp, "E001", "Ana", "Perez", "70234815", "Caja", "M", "8.5")
        registrar_empleado(emp, "E002", "Luis", "Rojas", "46321987", "Mesero", "T", "7")
        registrar_empleado(emp, "E003", "Rosa", "Diaz", "60562175", "Cocina", "M", "9")
        emp[2]["estado"] = "Inactivo"
        return emp

    def p61():
        invalidos = ["123566", "12", "@@ @@", "Juan", "", "   ", "Ana 123", "A1 B2", "Ana_Perez", "x" * 61 + " Perez"]
        validos = ["Ana Perez", "María Núñez-Peña", "O'Brien Smith", "  Luis   Rojas  "]
        lista = []
        aceptados = [n for n in invalidos if mod_usuarios.crear_usuario(lista, "usuario1", n, "Administrador", "Clave1234")[0]]
        lista = []
        creados = [mod_usuarios.crear_usuario(lista, f"usuario{i}", n, "Administrador", "Clave1234")[0] for i, n in enumerate(validos)]
        normalizado = lista[3]["nombre"] if len(lista) == 4 else None
        web3, c3, lista3, _ = web_nuevo(usuarios=[])
        c3.get("/configuracion-inicial")
        r = c3.post("/configuracion-inicial", data={"usuario": "jefe", "nombre": "123566", "clave": "Clave1234",
                                                    "clave2": "Clave1234", "csrf": csrf(c3)}, follow_redirects=True)
        web_rechaza = lista3 == [] and "Nombre invalido" in r.get_data(as_text=True)
        return (f"{len(invalidos)} nombres invalidos rechazados (123566, Juan, @@ @@...); {len(validos)} validos aceptados "
                f"(normalizado: {normalizado!r}); el formulario de primera vez rechaza '123566': {web_rechaza}"), (
            not aceptados and all(creados) and normalizado == "Luis Rojas" and web_rechaza)
    caso("P61", "Nombre completo del usuario: solo letras, al menos 2 palabras, sin numeros ni simbolos (ej: '123566' se rechaza)",
         "Los nombres invalidos se rechazan, incluso al crear el primer Administrador", p61)

    def p62():
        emp = empleados_prueba()
        lista = []
        def crea(usuario, rol, codigo):
            return mod_usuarios.crear_usuario(lista, usuario, "Persona Prueba", rol, "Clave1234", codigo, emp)
        sin_codigo = crea("usuarioa1", "Trabajador", "")[0]
        formato = crea("usuarioa2", "Trabajador", "X1")[0]
        inexistente = crea("usuarioa3", "Trabajador", "E999")[0]
        inactivo = crea("usuarioa4", "Trabajador", "E003")[0]
        ok_vinculado = crea("usuarioa5", "Trabajador", " e001 ")[0]
        repetido = crea("usuarioa6", "Trabajador", "E001")[0]
        admin_libre = crea("usuarioa7", "Administrador", "")[0]
        vinculo = [u["codigo_empleado"] for u in lista]
        return (f"sin codigo/formato malo/inexistente/inactivo/repetido -> {[sin_codigo, formato, inexistente, inactivo, repetido]}; "
                f"vinculado a E001 -> {ok_vinculado}; Administrador sin vinculo -> {admin_libre}; codigos guardados {vinculo}"), (
            not any([sin_codigo, formato, inexistente, inactivo, repetido]) and ok_vinculado and admin_libre and vinculo == ["E001", ""])
    caso("P62", "Una cuenta de Trabajador debe estar vinculada a un trabajador registrado, activo y sin otra cuenta",
         "Sin vinculo valido no se crea; el Administrador no necesita vinculo", p62)

    def p63():
        web, c, lista, aud = web_nuevo()           # trabajador1 esta vinculado a E001
        web.empleados.extend(empleados_prueba()[:2])
        entrar(c, "trabajador1", "Clave5678")
        t = csrf(c)
        ajena = c.post("/entrada", data={"csrf": t, "codigo": "E002", "fecha": HOY, "hora": "14:00", "turno": "Tarde"}, follow_redirects=True)
        ajena_bloqueada = "Solo puedes registrar tu propia asistencia" in ajena.get_data(as_text=True) and web.asistencias == []
        denegado_auditado = any(a[1] == "Acceso denegado" for a in aud)
        propia = c.post("/entrada", data={"csrf": t, "fecha": HOY, "hora": "08:00", "turno": "Mañana"})   # sin campo codigo
        c.post("/salida", data={"csrf": t, "codigo": "E001", "fecha": HOY, "hora": "16:00", "turno": "Mañana"})
        propia_ok = len(web.asistencias) == 1 and web.asistencias[0]["codigo_empleado"] == "E001" and web.asistencias[0]["hora_salida"] == "16:00"
        c.post("/logout", data={"csrf": t})
        entrar(c, "admin", "Clave1234")
        t = csrf(c)
        c.post("/entrada", data={"csrf": t, "codigo": "E002", "fecha": HOY, "hora": "14:00", "turno": "Tarde"})   # el Administrador si puede
        admin_ve = c.get("/?vista=asistencia").get_data(as_text=True)
        admin_marca_otro = any(r["codigo_empleado"] == "E002" for r in web.asistencias) and "<td>E001</td>" in admin_ve and "<td>E002</td>" in admin_ve
        c.post("/logout", data={"csrf": t})
        entrar(c, "trabajador1", "Clave5678")
        pagina = c.get("/?vista=asistencia&codigo=E002", follow_redirects=True).get_data(as_text=True)   # intenta ver la de otro
        solo_suyas = "<td>E001</td>" in pagina and "<td>E002</td>" not in pagina and "Solo ves tu propia asistencia" in pagina
        sin_campo_codigo = 'name="codigo"' not in pagina.split("Filtrar")[0] and "Tu cuenta" in pagina
        return (f"el Trabajador no puede marcar a otro (bloqueado y auditado: {ajena_bloqueada and denegado_auditado}); marca la suya: {propia_ok}; "
                f"el Administrador marca a cualquiera: {admin_marca_otro}; el Trabajador solo ve su asistencia: {solo_suyas}; "
                f"su formulario no tiene campo de codigo: {sin_campo_codigo}"), (
            ajena_bloqueada and denegado_auditado and propia_ok and admin_marca_otro and solo_suyas and sin_campo_codigo)
    caso("P63", "Web: el Trabajador solo marca y ve SU asistencia; el Administrador marca y ve la de todos",
         "Marcar a otro trabajador se bloquea y queda auditado; el Administrador no tiene esa restriccion", p63)

    def p64():
        emp = empleados_prueba()[:2]
        asi = []
        marcar_entrada(asi, emp, "E002", "2026-09-05", "14:30", "")          # ajena y con tardanza
        marcar_salida(asi, "E002", "2026-09-05", "20:00")
        lista = copy.deepcopy(USUARIOS_BASE)
        mod_usuarios.crear_usuario(lista, "sinvinculo", "Sin Vinculo", "Trabajador", "Clave9999")   # cuenta sin trabajador
        originales = (consola_controller.cargar_usuarios, consola_controller.cargar_empleados, consola_controller.cargar_asistencias)
        consola_controller.cargar_usuarios = lambda: lista
        consola_controller.cargar_empleados = lambda *a, **k: emp
        consola_controller.cargar_asistencias = lambda *a, **k: asi
        try:
            _, texto, _ = con_claves(consola_controller.main, ["T", "trabajador1", "4", "2026-09-01", "08:00", "", "5", "2026-09-01", "16:00",
                                                              "6", "7", "8", "0"], ["Clave5678"])
            como(None)
            _, texto_sin, _ = con_claves(consola_controller.main, ["T", "sinvinculo", "4", "0"], ["Clave9999"])
            como(None)
        finally:
            consola_controller.cargar_usuarios, consola_controller.cargar_empleados, consola_controller.cargar_asistencias = originales
        propia = [r for r in asi if r["codigo_empleado"] == "E001"]
        marco_suya = len(propia) == 1 and propia[0]["hora_salida"] == "16:00"
        sin_pedir_codigo = "Codigo del trabajador" not in texto
        no_ve_ajenas = "2026-09-05" not in texto and "E002" not in texto
        tardanzas_propias = "Total de tardanzas registradas: 0" in texto
        sin_vinculo = "no esta vinculado a un trabajador" in texto_sin
        return (f"el Trabajador marca su entrada y salida sin escribir codigo: {marco_suya and sin_pedir_codigo}; no ve asistencias ajenas: {no_ve_ajenas}; "
                f"cuenta las tardanzas solo de el: {tardanzas_propias}; cuenta sin vinculo -> mensaje: {sin_vinculo}"), (
            marco_suya and sin_pedir_codigo and no_ve_ajenas and tardanzas_propias and sin_vinculo)
    caso("P64", "Consola: el Trabajador usa su propio codigo (no lo pregunta) y solo ve su asistencia; una cuenta sin vinculo no puede marcar",
         "Marca y ve solo lo suyo; sin vinculo recibe un mensaje", p64)

    def p65():
        with tempfile.TemporaryDirectory() as tmp:
            bd = os.path.join(tmp, "asistencia.db")
            with closing(sqlite3.connect(bd)) as con:             # base creada ANTES del vinculo usuario-trabajador
                con.execute("CREATE TABLE usuarios (usuario TEXT PRIMARY KEY, nombre TEXT NOT NULL DEFAULT '', rol TEXT NOT NULL DEFAULT '', "
                            "clave_hash TEXT NOT NULL DEFAULT '', creado TEXT NOT NULL DEFAULT '')")
                con.execute("INSERT INTO usuarios VALUES ('viejo01', 'Viejo Usuario', 'Trabajador', 'x', '2026-01-01 10:00:00')")
                con.commit()
            usuarios = base_datos.cargar_usuarios(bd)
            with closing(sqlite3.connect(bd)) as con:
                columnas = [f[1] for f in con.execute("PRAGMA table_info(usuarios)")]
        return (f"columnas {columnas[-2:]}; el usuario anterior sigue y queda sin vinculo: {usuarios[0].get('codigo_empleado')!r}"), (
            "codigo_empleado" in columnas and len(usuarios) == 1 and usuarios[0]["usuario"] == "viejo01" and usuarios[0]["codigo_empleado"] == "")
    caso("P65", "Compatibilidad: una base anterior sin vinculo usuario-trabajador se actualiza al abrirla sin perder usuarios",
         "Se agrega la columna codigo_empleado y el usuario anterior se conserva", p65)

    def p66():
        admin = {"usuario": "admin", "rol": "Administrador", "codigo_empleado": ""}
        trabajador = {"usuario": "t1", "rol": "Trabajador", "codigo_empleado": "E001"}
        sin_vinculo = {"usuario": "t2", "rol": "Trabajador", "codigo_empleado": ""}
        pu = mod_usuarios.puede_ver_codigo
        tabla = [pu(admin, "E001"), pu(admin, "E002"), pu(trabajador, "E001"), pu(trabajador, " e001 "),
                 pu(trabajador, "E002"), pu(sin_vinculo, "E001"), pu(None, "E001")]
        propios = [mod_usuarios.codigo_propio(admin), mod_usuarios.codigo_propio(trabajador), mod_usuarios.codigo_propio(sin_vinculo)]
        return (f"puede_ver_codigo (admin E001/E002, trabajador E001/E001 con espacios/E002, sin vinculo, sin sesion) -> {tabla}; "
                f"codigo_propio -> {propios}"), (tabla == [True, True, True, True, False, False, False] and propios == [None, "E001", None])
    caso("P66", "Regla de asistencia propia: el Administrador ve todo; el Trabajador solo su codigo; sin vinculo o sin sesion, nada",
         "[True, True, True, True, False, False, False]", p66)

    def p67():
        web, c, lista, aud = web_nuevo()
        def intento(usuario, clave, campo_rol=None):
            cli = web.app.test_client()
            pagina = cli.get("/login").get_data(as_text=True)
            datos = {"csrf": csrf(cli), "usuario": usuario, "clave": clave}
            if campo_rol is not None:
                datos["rol"] = campo_rol  # campo manipulado: el servidor debe ignorarlo
            r = cli.post("/login", data=datos, follow_redirects=True)
            return cli.get("/").status_code == 200, pagina, r.get_data(as_text=True)
        admin_ok, pagina, _ = intento("admin", "Clave1234")
        trabajador_ok, _, _ = intento("trabajador1", "Clave5678")
        clave_mala, _, h3 = intento("admin", "ClaveMala99")
        campo_manipulado, _, _ = intento("admin", "Clave1234", "Trabajador")
        solo_usuario_clave = 'name="rol"' not in pagina and 'name="usuario"' in pagina and 'name="clave"' in pagina
        auditados = sum(1 for a in aud if a[1] == "Login fallido")
        return (f"El login web solo muestra usuario/clave: {solo_usuario_clave}; "
                f"Administrador entra: {admin_ok}; Trabajador entra: {trabajador_ok}; "
                f"rol manipulado no altera el rol real: {campo_manipulado}; "
                f"clave incorrecta rechazada: {not clave_mala}; intentos auditados: {auditados}"), (
            solo_usuario_clave and admin_ok and trabajador_ok and campo_manipulado
            and not clave_mala and auditados >= 1)
    caso("P67", "Web: el login solicita solo usuario y contraseña; el rol real procede de la base de datos",
         "No hay selector de rol; las cuentas válidas entran y manipular un campo rol no cambia los permisos", p67)

    def p68():
        lista = copy.deepcopy(USUARIOS_BASE)
        resultado, texto, usadas = con_claves(lambda: consola_controller.iniciar_sesion(lista),
                                              ["T", "admin", "X", "admin", "A", "admin"], ["Clave1234", "Clave1234", "Clave1234"])
        como(None)
        entro = resultado is not None and resultado["rol"] == "Administrador"
        rechazos = texto.count("Usuario, contraseña o rol incorrectos.")
        lista2 = copy.deepcopy(USUARIOS_BASE)
        fallo, texto2, _ = con_claves(lambda: consola_controller.iniciar_sesion(lista2), ["A", "trabajador1"] * 3, ["Clave5678"] * 3)
        como(None)
        return (f"Administrador eligiendo T o una letra invalida -> {rechazos} rechazos y a la tercera entra como A: {entro}; "
                f"Trabajador eligiendo A tres veces -> sesion {fallo}"), (
            entro and rechazos == 2 and fallo is None and "Demasiados intentos" in texto2)
    caso("P68", "Consola: el login pide el rol (A=Administrador / T=Trabajador) antes del usuario y la contraseña",
         "Un rol que no corresponde a la cuenta cuenta como intento fallido; a los 3 se cierra", p68)

    def p69():
        web, c, lista, aud = web_nuevo()
        web.empleados.extend(empleados_prueba()[:2])
        hoy = datetime.now().strftime("%Y-%m-%d")
        marcar_entrada(web.asistencias, web.empleados, "E001", hoy, "08:00", "")                   # abierta, puntual
        marcar_entrada(web.asistencias, web.empleados, "E002", hoy, "14:30", "")                   # con tardanza
        marcar_salida(web.asistencias, "E002", hoy, "20:00")
        entrar(c, "admin", "Clave1234")
        panel = c.get("/", follow_redirects=True).get_data(as_text=True)
        def cifra(texto):
            return re.search(rf'<b style="font-size:1.6rem">(\d+)</b><br>{texto}', panel)
        numeros = [cifra(t).group(1) if cifra(t) else None for t in ("trabajadores activos", "asistencias de hoy", "jornadas sin salida", "tardanzas del mes")]
        enlaces = "formato=excel" in panel and "formato=csv" not in panel and "formato=json" not in panel
        admin_ok = "Inicio del administrador" in panel and numeros == ["2", "2", "1", "1"] and enlaces and "Últimas asistencias registradas" in panel
        c.post("/logout", data={"csrf": csrf(c)})
        entrar(c, "trabajador1", "Clave5678")
        pagina = c.get("/", follow_redirects=True).get_data(as_text=True)
        sin_panel = c.get("/?vista=panel", follow_redirects=True).get_data(as_text=True)
        trab_ok = ("Marcar mi asistencia" in pagina and "Hola, Omar Trabajador" in pagina and "Inicio del administrador" not in pagina
                   and "Hoy entraste a las 08:00 AM. Falta marcar tu salida." in pagina and "No tienes permiso." in sin_panel)
        return (f"el Administrador empieza en su panel (cifras {numeros}, exportar solo a Excel: {enlaces}): {admin_ok}; "
                f"el Trabajador empieza en 'Marcar mi asistencia' con el estado de su jornada y no puede abrir el panel: {trab_ok}"), admin_ok and trab_ok
    caso("P69", "Web: cada rol empieza en su pantalla (panel del Administrador con resumen y exportaciones; Trabajador solo a marcar su asistencia)",
         "Panel con 4 cifras, ultimas asistencias y exportaciones; el Trabajador ve su estado de hoy", p69)

    # ---------- Correcciones: hora AM/PM, turno obligatorio, fecha de hoy, ojito y solo Excel ----------
    def p70():
        convertidas = {"8:05": "08:05", "08:05 AM": "08:05", "8:05 pm": "20:05", "12:30 AM": "00:30", "12:00 PM": "12:00",
                       "12:00 p. m.": "12:00", "1:00PM": "13:00", "14:30": "14:30"}
        invalidas = ["13:00 PM", "00:10 AM", "12:60 PM", "25:00", "8:5 AM", "", "abc"]
        conv_ok = all(normalizar_hora(k) == v for k, v in convertidas.items())
        inv_ok = all(normalizar_hora(k) is None for k in invalidas)
        mostradas = [formatear_hora_12(h) for h in ("08:05", "14:30", "00:15", "12:00", "23:59", "")]
        mostrar_ok = mostradas == ["08:05 AM", "02:30 PM", "12:15 AM", "12:00 PM", "11:59 PM", ""]
        web, c, lista, aud = web_nuevo()
        web.empleados.extend(empleados_prueba()[:2])
        entrar(c, "admin", "Clave1234")
        t = csrf(c)
        form = c.get("/?vista=asistencia").get_data(as_text=True)
        selects = all(f'name="{n}"' in form for n in ("hora_h", "hora_m", "hora_ap")) and 'type="time"' not in form
        c.post("/entrada", data={"csrf": t, "codigo": "E001", "fecha": HOY, "hora_h": "08", "hora_m": "15", "hora_ap": "AM", "turno": "Mañana"})
        c.post("/salida", data={"csrf": t, "codigo": "E001", "fecha": HOY, "hora_h": "04", "hora_m": "45", "hora_ap": "PM", "turno": "Mañana"})
        guardado = web.asistencias[0] if web.asistencias else {}
        guarda_24h = guardado.get("hora_entrada") == "08:15" and guardado.get("hora_salida") == "16:45"
        tabla = c.get("/?vista=asistencia").get_data(as_text=True)
        tabla_12h = "<td>08:15 AM</td><td>04:45 PM</td>" in tabla and "16:45" not in tabla
        mal = c.post("/entrada", data={"csrf": t, "codigo": "E002", "fecha": HOY, "hora_h": "13", "hora_m": "00", "hora_ap": "PM", "turno": "Tarde"},
                     follow_redirects=True).get_data(as_text=True)
        rechaza_mala = "Hora invalida" in mal and len(web.asistencias) == 1
        return (f"acepta 8:05 PM / 12:30 AM / 12:00 p. m. y rechaza 13:00 PM, 12:60 PM, vacio: {conv_ok and inv_ok}; se muestra {mostradas}; "
                f"formulario con hora 1-12, minutos y AM/PM (sin type=time): {selects}; guarda en 24 h: {guarda_24h}; "
                f"la tabla muestra 08:15 AM y 04:45 PM: {tabla_12h}; hora 13 PM rechazada: {rechaza_mala}"), (
            conv_ok and inv_ok and mostrar_ok and selects and guarda_24h and tabla_12h and rechaza_mala)
    caso("P70", "Web: las horas se escriben y se muestran en formato 12 h con AM/PM (se guardan en 24 h)",
         "Selectores hora/minutos/AM-PM; la tabla muestra 08:15 AM y 04:45 PM; hora invalida rechazada", p70)

    def p71():
        auto = [turno_segun_hora(h) for h in ("06:00", "13:59", "01:59 PM", "14:00", "02:00 PM", "11:30 PM")]
        auto_ok = auto == ["Mañana", "Mañana", "Mañana", "Tarde", "Tarde", "Tarde"] and turno_segun_hora("xx") is None
        web, c, lista, aud = web_nuevo()
        web.empleados.extend(empleados_prueba()[:2])
        entrar(c, "admin", "Clave1234")
        t = csrf(c)
        base = {"csrf": t, "codigo": "E001", "fecha": HOY, "hora": "08:00"}
        sin_e = c.post("/entrada", data={**base, "turno": ""}, follow_redirects=True).get_data(as_text=True)
        falso = c.post("/entrada", data={**base, "turno": "Noche"}, follow_redirects=True).get_data(as_text=True)
        sin_campo = c.post("/entrada", data=base, follow_redirects=True).get_data(as_text=True)
        nada_guardado = web.asistencias == []
        rechaza_entrada = all("Seleccione un turno" in x for x in (sin_e, falso, sin_campo)) and nada_guardado
        c.post("/entrada", data={**base, "turno": "Mañana"})
        sin_s = c.post("/salida", data={**base, "hora": "16:00", "turno": ""}, follow_redirects=True).get_data(as_text=True)
        sigue_abierta = len(web.asistencias) == 1 and web.asistencias[0]["hora_salida"] == ""
        rechaza_salida = "Seleccione un turno" in sin_s and sigue_abierta
        c.post("/salida", data={**base, "hora": "16:00", "turno": "Mañana"})
        con_turno = web.asistencias[0]["hora_salida"] == "16:00"
        form = c.get("/?vista=asistencia").get_data(as_text=True)
        esperado = turno_segun_hora(datetime.now().strftime("%H:%M"))
        sin_vacio = 'name="turno"' in form and "vacío = habitual" not in form and 'value=""' not in form.split('name="turno"')[1].split("</select>")[0]
        propuesto = re.search(rf'value="{esperado}"\s+selected', form) is not None
        return (f"turno automatico por hora (antes de las 14:00 Mañana, desde ahi Tarde): {auto_ok}; entrada sin turno / turno falso / sin campo rechazada: {rechaza_entrada}; "
                f"salida sin turno rechazada: {rechaza_salida}; con turno marca bien: {con_turno}; "
                f"el formulario no tiene opcion vacia: {sin_vacio}; propone '{esperado}' segun la hora actual: {propuesto}"), (
            auto_ok and rechaza_entrada and rechaza_salida and con_turno and sin_vacio and propuesto)
    caso("P71", "Web: no se marca entrada ni salida sin turno; el turno se propone solo segun la hora",
         "Sin turno el servidor rechaza; el formulario ya trae el turno de la hora actual", p71)

    def p72():
        web, c, lista, aud = web_nuevo()
        web.empleados.extend(empleados_prueba()[:2])
        entrar(c, "admin", "Clave1234")
        t = csrf(c)
        ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        manana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        rechazos = []
        for fecha in (ayer, manana, "01/09/2026", "2026-9-1", ""):
            r = c.post("/entrada", data={"csrf": t, "codigo": "E001", "fecha": fecha, "hora": "08:00", "turno": "Mañana"}, follow_redirects=True)
            rechazos.append("fecha de hoy" in r.get_data(as_text=True))
        nada = web.asistencias == []
        c.post("/entrada", data={"csrf": t, "codigo": "E001", "fecha": HOY, "hora": "08:00", "turno": "Mañana"})
        salida_ayer = c.post("/salida", data={"csrf": t, "codigo": "E001", "fecha": ayer, "hora": "16:00", "turno": "Mañana"}, follow_redirects=True)
        salida_rechazada = "fecha de hoy" in salida_ayer.get_data(as_text=True) and web.asistencias[0]["hora_salida"] == ""
        hoy_ok = len(web.asistencias) == 1 and web.asistencias[0]["fecha"] == HOY
        form = c.get("/?vista=asistencia").get_data(as_text=True)
        campo = re.search(r'<input[^>]*name="fecha"[^>]*>', form)
        campo = campo.group(0) if campo else ""
        bloqueado = f'value="{HOY}"' in campo and f'min="{HOY}"' in campo and f'max="{HOY}"' in campo and "readonly" in campo
        return (f"fecha de ayer, de mañana, 01/09/2026, 2026-9-1 y vacia rechazadas: {all(rechazos) and nada}; salida con fecha de ayer rechazada: {salida_rechazada}; "
                f"con la fecha de hoy ({HOY}) se registra: {hoy_ok}; el campo fecha trae hoy y no se puede cambiar (min=max=hoy, solo lectura): {bloqueado}"), (
            all(rechazos) and nada and salida_rechazada and hoy_ok and bloqueado)
    caso("P72", "Web: solo se marca con la fecha de hoy (ni pasadas ni futuras)",
         "Cualquier otra fecha se rechaza; el campo viene con la fecha actual y bloqueado", p72)

    def p73():
        web, c, lista, aud = web_nuevo()
        entrar(c, "admin", "Clave1234")
        r = c.get("/?vista=usuarios")
        pagina = r.get_data(as_text=True)
        csp = r.headers.get("Content-Security-Policy", "")
        ojos = [f'data-toggle="{n}"' in pagina for n in ("clave", "clave2")]
        campos = 'type="password" name="clave" id="clave"' in pagina and 'type="password" name="clave2" id="clave2"' in pagina
        accesible = pagina.count('aria-label="Mostrar contraseña"') == 2 and pagina.count("ojo-tachado") >= 2
        script = "classList.toggle('oculto'" in pagina and "campo.type = mostrar ? 'text' : 'password'" in pagina
        scripts_permitidos = "script-src 'self' 'unsafe-inline'" in csp
        coincidencia = 'id="coincidencia"' in pagina and "Las contraseñas no coinciden." in pagina
        login = web.app.test_client().get("/login").get_data(as_text=True)
        login_ok = 'data-toggle="clave"' in login and "ojo-abierto" in login and "◉" not in login
        return (f"Usuarios: ojito en contraseña y en repetir contraseña: {all(ojos)}; los campos son password por defecto: {campos}; "
                f"accesible (aria-label, icono ojo/ojo tachado): {accesible}; script de mostrar/ocultar: {script}; "
                f"la CSP permite el script: {scripts_permitidos}; aviso coinciden/no coinciden: {coincidencia}; login con el mismo ojito: {login_ok}"), (
            all(ojos) and campos and accesible and script and scripts_permitidos and coincidencia and login_ok)
    caso("P73", "Web: el apartado Usuarios (y el login) muestran un ojito para ver la contraseña escrita",
         "Dos ojitos en Usuarios, mismo script que el login, permitido por la CSP", p73)

    def p74():
        web, c, lista, aud = web_nuevo()
        web.empleados.extend(empleados_prueba()[:2])
        entrar(c, "admin", "Clave1234")
        panel = c.get("/").get_data(as_text=True)
        planilla = c.get(f"/?vista=planilla&mes={MES_HOY}").get_data(as_text=True)
        sin_botones = all("CSV" not in x and "JSON" not in x and "formato=csv" not in x and "formato=json" not in x for x in (panel, planilla))
        con_excel = "formato=excel" in panel and "formato=excel" in planilla
        rechazados = [c.get(f"/exportar?mes={MES_HOY}&formato={f}") for f in ("csv", "json", "pdf")]
        mensajes = c.get(f"/?vista=planilla&mes={MES_HOY}").get_data(as_text=True)
        solo_excel = all(r.status_code == 302 for r in rechazados)
        with tempfile.TemporaryDirectory() as tmp:
            web.exportar_a_excel = lambda e, a, planilla=None: exportar_a_excel(e, a, os.path.join(tmp, "r.xlsx"), planilla=planilla)
            xlsx = c.get(f"/exportar?mes={MES_HOY}&formato=excel")
            xlsx_ok = xlsx.status_code == 200 and xlsx.get_data()[:2] == b"PK"      # un .xlsx es un zip
        llamadas = []
        original = consola_controller.exportar_a_excel
        consola_controller.exportar_a_excel = lambda e, a, planilla=None: llamadas.append(1) or "reporte.xlsx"
        try:
            _, texto, usadas = con_entradas(lambda: consola_controller.opcion_exportar(web.empleados, []), ["2026-09"])
        finally:
            consola_controller.exportar_a_excel = original
        _, menu, _ = con_entradas(lambda: vista.mostrar_menu({"usuario": "a", "rol": "Administrador"}, {str(n) for n in range(1, 15)}), [])
        consola_ok = llamadas == [1] and usadas == 1 and "CSV" not in texto and "10. Exportar reporte a Excel" in menu and "CSV" not in menu
        return (f"web sin botones CSV/JSON y con Excel: {sin_botones and con_excel}; csv/json/pdf rechazados: {solo_excel}; Excel descarga un .xlsx: {xlsx_ok}; "
                f"consola solo pide el mes y genera Excel (menu '10. Exportar reporte a Excel'): {consola_ok}"), (
            sin_botones and con_excel and solo_excel and xlsx_ok and consola_ok)
    caso("P74", "La exportacion es solo a Excel (web y consola)",
         "Sin botones ni rutas de CSV/JSON; Excel funciona; la consola exporta solo a Excel", p74)

    consola_controller.registrar_auditoria = registrar_original
    como(None)

    consola_controller.guardar_empleados, consola_controller.guardar_asistencias = guardados

    HORA_TOPE_POR_TURNO.clear()
    HORA_TOPE_POR_TURNO.update(topes_reales)

    ok_total = sum(1 for r in RESULTADOS if r["ok"])
    print(f"\nRESUMEN: {ok_total}/{len(RESULTADOS)} casos correctos")
    return ok_total == len(RESULTADOS)


if __name__ == "__main__":
    todo_ok = ejecutar()
    if "--json" in sys.argv:
        destino = sys.argv[sys.argv.index("--json") + 1]
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(RESULTADOS, f, ensure_ascii=False, indent=1)
    sys.exit(0 if todo_ok else 1)
