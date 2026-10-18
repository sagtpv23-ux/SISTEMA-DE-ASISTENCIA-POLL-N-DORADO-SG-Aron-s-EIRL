"modulo de planilla mensual:"
"calcula el pago de mensual de cada trabajador a parti de las horas"
"trabajdas en un mes, separadas por dos turnos (Mañana y Tarde), teniendo"
"en cuenta también su tarifa por hora."

TURNOS = ("Mañana, Tarde")

def calcular_horas_mes_por_turno(lista_asistencias, codigo, mes):
    """
    Suma las horas trabajadas por un empleado en un mes ('AAAA-MM'),
    separadas por turno. Solo cuenta jornadas cerradas (con hora de salida).
    Retorna un diccionario: {"Mañana": horas, "Tarde": horas}.
    """
    codigo = codigo.strip().upper()
    horas = {turno: 0.0 for turno in TURNOS}
    for registro in lista_asistencias:
        if(
            registro["codigo_trabajador"] == codigo
            and registro["fecha"].startswith(mes)
            and registro["horas_trabajadas"] !=""
        ):
            try:
                horas_registro = float(registro["horas_trabajadas"])
            except (ValueError, TypeError):
                #Dato corrupto (el: archivo editado a mano): se omite el registro
                continue
            turno = registro.get("turno", "")
            if turno in horas:
                horas[turno] += horas_registro
    return {turno: round(total, 2) for turno, total in horas.items()}

def calcular_horas_mes(lista_asistencias, codigo, mes):
    """Total de horas del mes (suma de ambos turnos)."""
    por_turno = calcular_horas_mes_por_turno(lista_asistencias, codigo, mes)
    return round(sum(por_turno.values()), 2)  

def calcular_pago_mensual(trabajador, lista_asistencias, mes):
    """
    Pago de un trabajador en un mes: (horas Mañana + horas Tarde) x tarifa_hora.
    Retorna un diccionario con el detalle del calculo.
    """
    por_turno = calcular_horas_mes_por_turno(lista_asistencias,trabajador["codigo"], mes )
    total_horas = round(sum(por_turno.values(), 2)) 
    try:
        tarifa = float(trabajador["tarifa_hora"])  
    except (ValueError, TypeError):
        tarifa = 0.0 #tarifa ausente o inválida: no se puede calcular el pago
    return {
        "codigo": trabajador["codigo"],
        "nombres": trabajador["nombres"],
        "apellidos": trabajador["apellidos"],
        "mes": mes,
        "horas_mañana": por_turno["mañana"],
        "horas_tarde": por_turno["tarde"],
        "horas_trabajadas": total_horas,
        "tarifa_hora": tarifa,
        "pago_mensual": round(total_horas * tarifa, 2),
    } 

def generar_planilla_mensual(lista_trabajadores, lista_asistencias, mes):
    """
    Planilla completa: el pago de cada trabajador activo para el mes indicado.
    Retorna una lista de diccionarios (un registro por trabajador).
    """
    planilla = []
    for trabajador in lista_trabajadores:
        if trabajador["estado"] == "ACTIVO":
            planilla.append(calcular_pago_mensual(trabajador, lista_asistencias, mes))
    return planilla

def total_planilla(planilla):
    """Suma el pago_mensual de todos los registros de una planilla."""
    return round(sum(registro["pago_mensual"] for registro in planilla), 2)

def contar_jornadas_mes(lista_asistencias, codigo, mes):
    """
    Cuenta las jornadas de un trabajador en un mes: (cerradas, abiertas).
    Una jornada abierta es una entrada a la que le falta la hora de salida.
    """
    codigo = codigo.strip().upper()
    cerradas = 0
    abiertas = 0
    for registro in lista_asistencias:
        if registro["codigo_trabajador"] == codigo and registro["fecha"].startswith(mes):
            if registro["hora_salida"] == "":
                abiertas += 1
            else:
                cerradas += 1
    return cerradas, abiertas

def meses_con_datos(lista_asistencias):
    """Lista ordenada de los meses (AAAA-MM) que tienen asistencias registradas."""
    meses = []   
    for registro in lista_asistencias:
        mes = registro["fecha"][:7]
        if mes not in meses:
            meses.append(mes)
    meses.sort()  
    return meses