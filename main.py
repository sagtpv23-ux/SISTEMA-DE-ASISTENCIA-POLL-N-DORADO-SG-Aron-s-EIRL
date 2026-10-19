"""
Sistema de Asistencia de Trabajadores - SG Aron's EIRL (Pollon Dorado)
Programa principal: menu de estructuras de control que integra
todos los modulos del prototipo.
"""

from modulo_trabajadores import (
    registrar_empleado,
    listar_empleados,
    ordenar_empleados_por_codigo,
    buscar_binario_recursivo,
)
from modulo_asistencia import (
    marcar_entrada,
    marcar_salida,
    buscar_asistencias_por_codigo,
    ordenar_asistencias_por_fecha,
    contar_tardanzas_recursivo,
    completar_turnos,
)
from modulo_persistencia import (
    cargar_empleados,
    guardar_asistencias,
    cargar_asistencias,
)

import os
from modulo_reportes import exportar_a_excel

from modulo_planilla import (
    generar_planilla_mensual,
    total_planilla,
    contar_jornadas_mes,
    meses_con_datos,
)
from modulo_validaciones import validar_formato_mes


def mostrar_menu():
    print("\n===== SISTEMA DE ASISTENCIA - SG ARON'S EIRL =====")
    print("1. Registrar trabajador")
    print("2. Listar trabajadores")
    print("3. Buscar trabajador por codigo")
    print("4. Marcar entrada")
    print("5. Marcar salida")
    print("6. Ver asistencias de un trabajador")
    print("7. Ver todas las asistencias ordenadas por fecha")
    print("8. Contar tardanzas totales")
    print("9. Generar planilla mensual (pago por horas)")
    print("10. Exportar reporte completo a Excel")
    print("0. Salir")


def mostrar_asistencia(r):
    """Imprime un registro de asistencia en una linea legible."""
    salida = r["hora_salida"] if r["hora_salida"] else "--:--"
    horas = r["horas_trabajadas"] if r["horas_trabajadas"] != "" else "-"
    print(
        f"{r['fecha']} | {r['codigo_empleado']} | {r['turno']:<6} | "
        f"{r['hora_entrada']} - {salida} | {horas} h | Tardanza: {r['tardanza']}"
    )


def pedir_mes():
    """Pide el mes (AAAA-MM) y lo valida. Retorna el mes o None si es invalido."""
    mes = input("Mes (AAAA-MM, ej: 2026-09): ").strip()
    if not validar_formato_mes(mes):
        print("Mes invalido. Formato esperado: AAAA-MM (ej: 2026-09).")
        return None
    return mes


def main():
    lista_empleados = cargar_empleados()
    lista_asistencias = cargar_asistencias()

    # Archivos de versiones anteriores: asignar el turno habitual a jornadas sin turno
    antiguos = completar_turnos(lista_asistencias, lista_empleados)
    if antiguos:
        print(f"Aviso: {antiguos} asistencia(s) de una version anterior no tenian turno;")
        print("       se les asigno el turno habitual del trabajador.")

    try:
        while True:
            mostrar_menu()
            opcion = input("Elige una opcion: ").strip()

            if opcion == "1":
                codigo = input("Codigo (ej: E001): ")
                nombres = input("Nombres: ")
                apellidos = input("Apellidos: ")
                dni = input("DNI: ")
                cargo = input("Cargo (Parrillero/Mesero/Caja/Cocina/Administracion): ")
                turno = input("Turno habitual (M=Mañana / T=Tarde): ")
                tarifa_hora = input("Tarifa por hora en soles (ej: 8.5): ")
                ok, mensaje = registrar_empleado(
                    lista_empleados, codigo, nombres, apellidos, dni, cargo, turno, tarifa_hora
                )
                print(mensaje)
                if ok:
                    pass
                    # guardar_empleados(lista_empleados)

            elif opcion == "2":
                empleados = listar_empleados(lista_empleados)
                if not empleados:
                    print("No hay trabajadores registrados.")
                for e in empleados:
                    print(
                        f"{e['codigo']} - {e['nombres']} {e['apellidos']} - {e['cargo']} - "
                        f"{e['turno']} - S/ {e['tarifa_hora']} por hora"
                    )

            elif opcion == "3":
                codigo = input("Codigo a buscar: ")
                # La busqueda binaria requiere la lista ordenada por codigo
                ordenados = ordenar_empleados_por_codigo(lista_empleados)
                resultado = buscar_binario_recursivo(ordenados, codigo)
                if resultado:
                    print(
                        f"Encontrado: {resultado['codigo']} - {resultado['nombres']} "
                        f"{resultado['apellidos']} ({resultado['cargo']}, turno {resultado['turno']})"
                    )
                else:
                    print("Trabajador no encontrado.")

            elif opcion == "4":
                codigo = input("Codigo del trabajador: ")
                fecha = input("Fecha (AAAA-MM-DD): ")
                hora = input("Hora de entrada (HH:MM): ")
                turno = input("Turno de la jornada (M/T, Enter = turno habitual): ")
                ok, mensaje = marcar_entrada(lista_asistencias, lista_empleados, codigo, fecha, hora, turno)
                print(mensaje)
                if ok:
                    guardar_asistencias(lista_asistencias)

            elif opcion == "5":
                codigo = input("Codigo del trabajador: ")
                fecha = input("Fecha (AAAA-MM-DD): ")
                hora = input("Hora de salida (HH:MM): ")
                ok, mensaje = marcar_salida(lista_asistencias, codigo, fecha, hora)
                print(mensaje)
                if ok:
                    guardar_asistencias(lista_asistencias)

            elif opcion == "6":
                codigo = input("Codigo del trabajador: ")
                registros = buscar_asistencias_por_codigo(lista_asistencias, codigo)
                if not registros:
                    print("No hay registros para ese trabajador.")
                for r in registros:
                    mostrar_asistencia(r)

            elif opcion == "7":
                if not lista_asistencias:
                    print("No hay asistencias registradas.")
                for r in ordenar_asistencias_por_fecha(lista_asistencias):
                    mostrar_asistencia(r)

            elif opcion == "8":
                total = contar_tardanzas_recursivo(lista_asistencias)
                print(f"Total de tardanzas registradas: {total}")

            elif opcion == "9":
                mes = pedir_mes()
                if mes:
                    planilla = generar_planilla_mensual(lista_empleados, lista_asistencias, mes)
                    if not planilla:
                        print("No hay trabajadores activos registrados.")
                    for p in planilla:
                        print(
                            f"{p['codigo']} - {p['nombres']} {p['apellidos']}: "
                            f"Mañana {p['horas_manana']} h + Tarde {p['horas_tarde']} h = "
                            f"{p['horas_trabajadas']} h x S/ {p['tarifa_hora']} = S/ {p['pago_mensual']}"
                        )
                        if p["horas_trabajadas"] == 0:
                            # Explicar por que sale en cero (no es un error del programa)
                            cerradas, abiertas = contar_jornadas_mes(lista_asistencias, p["codigo"], mes)
                            if abiertas:
                                print(f"   Aviso: {abiertas} jornada(s) sin hora de salida (use la opcion 5).")
                            elif not cerradas:
                                print(f"   Aviso: este trabajador no tiene asistencias en {mes}.")
                    print(f"TOTAL PLANILLA {mes}: S/ {total_planilla(planilla)}")
                    if total_planilla(planilla) == 0 and lista_asistencias:
                        print("Meses con asistencias registradas: " + ", ".join(meses_con_datos(lista_asistencias)))

            elif opcion == "10":
                mes = pedir_mes()
                if mes:
                    planilla = generar_planilla_mensual(lista_empleados, lista_asistencias, mes)
                    ruta = exportar_a_excel(lista_empleados, lista_asistencias, planilla=planilla)
                    if ruta:
                        print(f"Reporte generado: {ruta}")

            elif opcion == "0":
                print("Hasta luego.")
                break

            else:
                print("Opcion invalida.")

    except (KeyboardInterrupt, EOFError):
        # Ctrl+C o fin de la entrada: se sale ordenadamente sin perder datos
        print("\nPrograma interrumpido por el usuario.")
    finally:
        # guardar_empleados(lista_empleados)
        guardar_asistencias(lista_asistencias)


if __name__ == "__main__":
    main()