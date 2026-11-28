"""
MODELO - Acceso a datos (SQLite).

Guarda y carga empleados y asistencias en una base de datos SQLite
(data/asistencia.db). SQLite viene incluido con Python (modulo sqlite3): no hay
que instalar nada ni levantar ningun servidor; la base es un solo archivo.

Las funciones publicas trabajan con listas de diccionarios, por eso los
controladores y las pruebas no necesitan saber como se guardan los datos.

- UTF-8: SQLite almacena el texto en UTF-8, asi que se admiten tildes, ñ, ü, ç...
- La primera vez que se crea la base, si existen los CSV de versiones anteriores
  (data/empleados.csv y data/asistencias.csv), sus datos se importan solos.
- Cada guardado es una transaccion: si algo falla, la base queda como estaba.
- Usa manejo de excepciones para no cerrar el programa si la base esta
  bloqueada, no se puede escribir o esta dañada.
- Tambien guarda los USUARIOS del sistema (tabla usuarios) y el historial de
  cambios (tabla auditoria). La auditoria solo admite INSERT: unos triggers de
  SQLite impiden modificar o borrar registros ya guardados.
"""

import csv
import os
import sqlite3
from contextlib import closing

# La base de datos se guarda en la carpeta "data" junto a este modulo
# La carpeta "data" esta en la raiz del proyecto (un nivel arriba de models/)
CARPETA_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RUTA_BD = os.path.join(CARPETA_DATA, "asistencia.db")

# CSV de versiones anteriores: solo se usan para importar sus datos a SQLite
ARCHIVO_EMPLEADOS_CSV = os.path.join(CARPETA_DATA, "empleados.csv")
ARCHIVO_ASISTENCIAS_CSV = os.path.join(CARPETA_DATA, "asistencias.csv")
CODIFICACION_CSV = "utf-8-sig"  # lee UTF-8 con o sin BOM (el que genera Excel)

CAMPOS_EMPLEADOS = ["codigo", "nombres", "apellidos", "dni", "cargo", "turno", "tarifa_hora", "estado"]
CAMPOS_ASISTENCIAS = [
    "codigo_empleado",
    "fecha",
    "turno",
    "hora_entrada",
    "hora_salida",
    "horas_trabajadas",
    "tardanza",
    "observaciones",
]

CAMPOS_USUARIOS = ["usuario", "nombre", "rol", "clave_hash", "creado", "codigo_empleado"]
CAMPOS_AUDITORIA = ["usuario", "accion", "entidad", "detalle", "fecha_hora"]

# Tablas. Todo se guarda como TEXTO (igual que antes en los CSV), de modo que el
# resto del programa recibe exactamente los mismos valores.
ESQUEMA = """
CREATE TABLE IF NOT EXISTS empleados (
    codigo       TEXT PRIMARY KEY,
    nombres      TEXT NOT NULL DEFAULT '',
    apellidos    TEXT NOT NULL DEFAULT '',
    dni          TEXT NOT NULL DEFAULT '',
    cargo        TEXT NOT NULL DEFAULT '',
    turno        TEXT NOT NULL DEFAULT '',
    tarifa_hora  TEXT NOT NULL DEFAULT '',
    estado       TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS asistencias (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_empleado   TEXT NOT NULL DEFAULT '',
    fecha             TEXT NOT NULL DEFAULT '',
    turno             TEXT NOT NULL DEFAULT '',
    hora_entrada      TEXT NOT NULL DEFAULT '',
    hora_salida       TEXT NOT NULL DEFAULT '',
    horas_trabajadas  TEXT NOT NULL DEFAULT '',
    tardanza          TEXT NOT NULL DEFAULT '',
    observaciones     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_asistencias_codigo_fecha
    ON asistencias (codigo_empleado, fecha);
CREATE TABLE IF NOT EXISTS usuarios (
    usuario      TEXT PRIMARY KEY,
    nombre       TEXT NOT NULL DEFAULT '',
    rol          TEXT NOT NULL DEFAULT '',
    clave_hash   TEXT NOT NULL DEFAULT '',
    creado       TEXT NOT NULL DEFAULT '',
    codigo_empleado TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS auditoria (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario      TEXT NOT NULL DEFAULT '',
    accion       TEXT NOT NULL DEFAULT '',
    entidad      TEXT NOT NULL DEFAULT '',
    detalle      TEXT NOT NULL DEFAULT '',
    fecha_hora   TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS auditoria_no_modificar
    BEFORE UPDATE ON auditoria
    BEGIN SELECT RAISE(ABORT, 'La auditoria no se puede modificar'); END;
CREATE TRIGGER IF NOT EXISTS auditoria_no_borrar
    BEFORE DELETE ON auditoria
    BEGIN SELECT RAISE(ABORT, 'La auditoria no se puede borrar'); END;
UPDATE usuarios SET rol = 'Trabajador' WHERE rol = 'Operador';
"""


# ----------------------------------------------------------------- seguridad (SQL)
# Proteccion contra inyeccion SQL:
#  1) Los VALORES (lo que escribe el usuario) siempre viajan como parametros (?),
#     nunca se concatenan dentro del texto SQL: SQLite los trata solo como datos.
#  2) Los nombres de tabla y de columnas no vienen del usuario: salen de estas
#     constantes y ademas se verifican contra una lista blanca antes de armar la consulta.
TABLAS_PERMITIDAS = {
    "empleados": CAMPOS_EMPLEADOS,
    "asistencias": CAMPOS_ASISTENCIAS,
    "usuarios": CAMPOS_USUARIOS,
    "auditoria": CAMPOS_AUDITORIA,
}


def _verificar_tabla(tabla, campos):
    if tabla not in TABLAS_PERMITIDAS or list(campos) != TABLAS_PERMITIDAS[tabla]:
        raise ValueError(f"Tabla o columnas no permitidas: {tabla!r}")


# ----------------------------------------------------------------- utilidades
def _abrir(ruta):
    """Abre (o crea) la base y sus tablas. Retorna (conexion, es_nueva)."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)  # crea data/ la primera vez
    es_nueva = not os.path.exists(ruta)
    conexion = sqlite3.connect(ruta, timeout=5)
    # Endurecimiento de SQLite: espera limitada, integridad referencial y menor
    # superficie para esquemas manipulados. WAL mejora la convivencia de lecturas.
    conexion.execute("PRAGMA busy_timeout = 5000")
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.execute("PRAGMA trusted_schema = OFF")
    conexion.execute("PRAGMA journal_mode = WAL")
    # Limites para reducir el impacto de entradas/formularios excesivamente grandes.
    if hasattr(conexion, "setlimit"):
        conexion.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 100_000)
        conexion.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)
        conexion.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 100)
    conexion.executescript(ESQUEMA)
    # Bases creadas antes del vinculo usuario-trabajador: se agrega la columna que falta
    columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(usuarios)")}
    if "codigo_empleado" not in columnas:
        conexion.execute("ALTER TABLE usuarios ADD COLUMN codigo_empleado TEXT NOT NULL DEFAULT ''")
        conexion.commit()
    return conexion, es_nueva


def _conectar(ruta):
    """Como _abrir, pero en la primera creacion de la base por defecto importa los CSV viejos."""
    conexion, es_nueva = _abrir(ruta)
    if es_nueva and os.path.abspath(ruta) == os.path.abspath(RUTA_BD):
        try:
            n_emp, n_asi = _importar(conexion, ARCHIVO_EMPLEADOS_CSV, ARCHIVO_ASISTENCIAS_CSV)
            if n_emp or n_asi:
                print(f"[INFO] Datos de los CSV anteriores importados a SQLite: "
                      f"{n_emp} trabajador(es) y {n_asi} asistencia(s).")
        except sqlite3.Error as error:
            print(f"[ADVERTENCIA] No se pudieron importar los CSV anteriores ({error}).")
    return conexion


def _leer_csv(ruta, campos):
    """Lee un CSV viejo como lista de diccionarios; completa con vacio las columnas que falten."""
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, mode="r", newline="", encoding=CODIFICACION_CSV) as archivo:
            filas = [fila for fila in csv.DictReader(archivo)]
    except (OSError, csv.Error, UnicodeDecodeError) as error:
        print(f"[ADVERTENCIA] No se pudo leer '{ruta}' ({error}). Se omite.")
        return []
    for fila in filas:
        for campo in campos:
            if fila.get(campo) is None:
                fila[campo] = ""
    return filas


def _texto(valor):
    """Valor a guardar como texto (None se guarda como cadena vacia)."""
    return "" if valor is None else str(valor)


def _insertar(conexion, tabla, campos, filas, ignorar_repetidos=False):
    _verificar_tabla(tabla, campos)
    sentencia = "INSERT OR IGNORE" if ignorar_repetidos else "INSERT"
    marcas = ", ".join("?" for _ in campos)
    conexion.executemany(
        f"{sentencia} INTO {tabla} ({', '.join(campos)}) VALUES ({marcas})",
        [tuple(_texto(fila.get(campo)) for campo in campos) for fila in filas],
    )


def _importar(conexion, ruta_empleados_csv, ruta_asistencias_csv):
    empleados = _leer_csv(ruta_empleados_csv, CAMPOS_EMPLEADOS)
    asistencias = _leer_csv(ruta_asistencias_csv, CAMPOS_ASISTENCIAS)
    with conexion:  # una sola transaccion
        _insertar(conexion, "empleados", CAMPOS_EMPLEADOS, empleados, ignorar_repetidos=True)
        _insertar(conexion, "asistencias", CAMPOS_ASISTENCIAS, asistencias)
    return len(empleados), len(asistencias)


def _guardar(ruta, tabla, campos, filas):
    """Reemplaza el contenido de la tabla por 'filas' en UNA transaccion. True si tuvo exito."""
    _verificar_tabla(tabla, campos)
    try:
        with closing(_conectar(ruta)) as conexion:
            with conexion:  # si falla algo, se deshace todo (rollback)
                conexion.execute(f"DELETE FROM {tabla}")
                _insertar(conexion, tabla, campos, filas)
        return True
    except (sqlite3.Error, OSError) as error:
        print(f"[ERROR] No se pudo guardar en la base de datos '{ruta}': {error}")
        return False


def _cargar(ruta, tabla, campos):
    """Retorna la tabla como lista de diccionarios (en el orden en que se guardo)."""
    _verificar_tabla(tabla, campos)
    try:
        with closing(_conectar(ruta)) as conexion:
            filas = conexion.execute(
                f"SELECT {', '.join(campos)} FROM {tabla} ORDER BY rowid"
            ).fetchall()
        return [dict(zip(campos, fila)) for fila in filas]
    except (sqlite3.Error, OSError) as error:
        print(f"[ADVERTENCIA] No se pudo leer la base de datos '{ruta}' ({error}).")
        print("              Se inicia con una lista vacia.")
        return []


# ----------------------------------------------------------- funciones publicas
def guardar_empleados(lista_empleados, ruta=RUTA_BD):
    return _guardar(ruta, "empleados", CAMPOS_EMPLEADOS, lista_empleados)


def cargar_empleados(ruta=RUTA_BD):
    return _cargar(ruta, "empleados", CAMPOS_EMPLEADOS)


def guardar_asistencias(lista_asistencias, ruta=RUTA_BD):
    return _guardar(ruta, "asistencias", CAMPOS_ASISTENCIAS, lista_asistencias)


def cargar_asistencias(ruta=RUTA_BD):
    return _cargar(ruta, "asistencias", CAMPOS_ASISTENCIAS)


def importar_desde_csv(ruta_empleados_csv=ARCHIVO_EMPLEADOS_CSV,
                       ruta_asistencias_csv=ARCHIVO_ASISTENCIAS_CSV, ruta=RUTA_BD):
    """
    Importa a SQLite los datos de los CSV de versiones anteriores (UTF-8 con o sin BOM).
    Agrega a lo que ya haya en la base (los codigos de trabajador repetidos se ignoran).
    Retorna (trabajadores_leidos, asistencias_leidas), o None si hubo un error.
    """
    try:
        with closing(_abrir(ruta)[0]) as conexion:
            return _importar(conexion, ruta_empleados_csv, ruta_asistencias_csv)
    except (sqlite3.Error, OSError) as error:
        print(f"[ERROR] No se pudo importar a '{ruta}': {error}")
        return None


# ------------------------------------------------------- usuarios y auditoria
def cargar_usuarios(ruta=RUTA_BD):
    """Retorna los usuarios del sistema como lista de diccionarios."""
    return _cargar(ruta, "usuarios", CAMPOS_USUARIOS)


def insertar_usuario(usuario, ruta=RUTA_BD):
    """
    Agrega UN usuario (diccionario con CAMPOS_USUARIOS). No reemplaza la tabla.
    Retorna True si se guardo, False si ya existe o hubo un error.
    """
    try:
        with closing(_conectar(ruta)) as conexion:
            with conexion:
                _insertar(conexion, "usuarios", CAMPOS_USUARIOS, [usuario])
        return True
    except (sqlite3.Error, OSError) as error:
        print(f"[ERROR] No se pudo guardar el usuario: {error}")
        return False


def insertar_auditoria(registro, ruta=RUTA_BD):
    """Agrega UN registro al historial (diccionario con CAMPOS_AUDITORIA). True si se guardo."""
    try:
        with closing(_conectar(ruta)) as conexion:
            with conexion:
                _insertar(conexion, "auditoria", CAMPOS_AUDITORIA, [registro])
        return True
    except (sqlite3.Error, OSError) as error:
        print(f"[ERROR] No se pudo registrar en la auditoria: {error}")
        return False


def cargar_auditoria(limite=200, ruta=RUTA_BD):
    """Retorna los ultimos 'limite' registros del historial, del mas reciente al mas antiguo."""
    _verificar_tabla("auditoria", CAMPOS_AUDITORIA)
    try:
        with closing(_conectar(ruta)) as conexion:
            filas = conexion.execute(
                f"SELECT {', '.join(CAMPOS_AUDITORIA)} FROM auditoria ORDER BY id DESC LIMIT ?",
                (int(limite),),
            ).fetchall()
        return [dict(zip(CAMPOS_AUDITORIA, fila)) for fila in filas]
    except (sqlite3.Error, OSError, ValueError) as error:
        print(f"[ADVERTENCIA] No se pudo leer la auditoria ({error}).")
        return []
