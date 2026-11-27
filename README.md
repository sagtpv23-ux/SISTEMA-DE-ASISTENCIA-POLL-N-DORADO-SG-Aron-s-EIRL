# Sistema de control de asistencia - SG Aron's EIRL (Pollón Dorado)

Proyecto del curso Fundamentos de Programación (CIIN1205P) - UPN.
Es un prototipo en Python para el restaurante Pollón Dorado, con menú de consola y también con interfaz web que se abre en Chrome. Incluye inicio de sesión con usuarios y roles, auditoría (historial de cambios), base de datos SQLite y exportación a Excel.

### 1. CORE / Problemática

En SG Aron's EIRL el control de asistencia se hace en un cuaderno. Ese es el problema central.

- A veces no anotan la hora exacta de entrada y salida.
- No se controlan las tardanzas porque hay 2 turnos (Mañana y Tarde) y cada uno entra a distinta hora.
- La planilla se saca a mano al final del mes, contando horas con calculadora y se equivocan.
- No hay reportes, si quieren ver faltas tienen que revisar el cuaderno hoja por hoja.

Eso genera que se pague mal, que haya reclamos y desorden en los turnos.

### 2. Objetivo general

Hacer un sistema en Python que registre las entradas y salidas, que detecte solo si es tardanza según el turno, y que calcule al final del mes cuantas horas trabajó cada persona y cuanto se le paga. Todo se exporta a Excel.

### 3. Objetivos específicos

- Registrar trabajadores con código tipo E001, nombres, DNI, cargo, turno y tarifa por hora.
- Marcar entrada y salida por turno.
- Calcular horas trabajadas y si hubo tardanza (Mañana tope 08:00, Tarde tope 14:00).
- Guardar los datos en una base de datos SQLite (data/asistencia.db) para que no se pierdan al cerrar.
- Generar planilla mensual (horas x tarifa).
- Exportar reporte a Excel con 3 hojas (Empleados, Asistencias y Planilla mensual). La exportación es **solo a Excel**.
- Pedir **usuario y contraseña** para entrar (contraseñas con hash PBKDF2, nunca en texto plano) y separar permisos por rol: Administrador y Trabajador.
- Llevar una **auditoría**: cada Insertar, Modificar, Eliminar, Buscar, Exportar, Login y Logout queda registrado con usuario, acción y fecha/hora, y no se puede editar ni borrar.
- Poder **modificar** y **eliminar** trabajadores (si ya tienen asistencias se les da de baja para no perder el historial).
- Cumplir con lo del curso: búsqueda binaria recursiva y recursividad. El ordenamiento usa `sorted()` de Python (Timsort, O(n log n)): se retiraron burbuja y selección porque solo sirven para proyectos pequeños (O(n²)).
- Organizar el código con la arquitectura MVC (models, views y controllers).
- Ofrecer una interfaz web (Flask + HTML) que se abre sola en Chrome a pantalla completa y usa los mismos módulos.
- Trabajar todo en UTF-8 para aceptar tildes, ñ y otros caracteres especiales.

### 4. Integrantes

- Arias Correa, Evelin Milagritos - models/validaciones.py y pruebas.py
- Luicho Mosqueira, Hector Alexander - models/empleado.py
- Mosqueira Tanta, Saul Alexander - models/asistencia.py
- Ocas Perez, Daniel Alexander - models/base_datos.py y views/reporte_excel.py
- Valdez Quiroz, Victor Paul - models/planilla.py, main.py y controllers/

### 5. Requisitos

Python 3.8 o superior.
SQLite ya viene incluido con Python (módulo sqlite3), no hay que instalar nada para la base de datos.
Instalar openpyxl (para el Excel) y flask (para la interfaz web). El hash de contraseñas usa solo la librería estándar:

pip install -r requirements.txt

Si no funciona:

pip install openpyxl flask

### 6. Como ejecutar

Abrir la carpeta del proyecto en terminal y poner:

python main.py     # abre el menú principal en la consola
python app_web.py  # abre la interfaz web en Chrome (pantalla completa, F11 para salir)
python pruebas.py  # corre las 69 pruebas, tiene que salir 69/69 (no toca la carpeta data/)

**Primera vez:** no existe ningún usuario ni contraseña por defecto. Tanto la consola como la web piden crear primero el usuario Administrador. Después hay que iniciar sesión cada vez.

La interfaz web queda en http://127.0.0.1:5000 y la terminal debe seguir abierta mientras se usa (Ctrl + C la detiene).

### 7. Estructura de carpetas (arquitectura MVC)

El código está organizado con el patrón **MVC (Modelo - Vista - Controlador)**, que separa las tres capas del sistema:

| Capa | Carpeta | Qué hace | Equivale a |
|---|---|---|---|
| Modelo | `models/` | Datos y reglas del negocio: validar, registrar, calcular horas, tardanzas y planilla, y guardar en SQLite. No sabe nada de pantallas. | Lógica de negocio |
| Vista | `views/` | Lo que el usuario ve: menú y mensajes de la consola, la página web (HTML) y el reporte en Excel. No calcula nada. | Lógica de presentación |
| Controlador | `controllers/` | Recibe lo que el usuario pide (una opción del menú o un clic en la web), llama a los modelos y elige qué vista mostrar. | Lógica de interacción |

Regla de dependencias: los modelos no importan vistas ni controladores, y las vistas no importan controladores (lo comprueba la prueba P38). Así, la misma lógica de negocio sirve para la consola y para la web.

```
PROYECTO_FINAL_EP-FUNDAMENTOS/
├── main.py                       Entrada de la versión de consola
├── app_web.py                    Entrada de la versión web (abre Chrome)
├── models/                       MODELO: datos y reglas de negocio
│   ├── validaciones.py           Reglas de validación (código, DNI, turno, fecha, hora, mes)
│   ├── empleado.py               Registro, búsqueda (lineal y binaria recursiva) y orden por código
│   ├── asistencia.py             Entrada/salida, horas, tardanza por turno, orden por fecha
│   ├── planilla.py               Horas del mes por turno y pago mensual
│   ├── usuarios.py               Usuarios, roles, hash PBKDF2 de contraseñas y autenticación
│   ├── auditoria.py              Historial de cambios (quién, qué y cuándo)
│   └── base_datos.py             Base de datos SQLite: guarda y carga empleados y asistencias
├── views/                        VISTA: lo que el usuario ve
│   ├── consola.py                Menú, mensajes y captura de datos por teclado
│   ├── reporte_excel.py          Exportación a Excel (.xlsx)
│   ├── reporte_csv.py            (sin uso: la exportación es solo a Excel)
│   ├── reporte_json.py           (sin uso: la exportación es solo a Excel)
│   └── templates/
│       ├── index.html            Página web (HTML + CSS): Trabajadores, Asistencia, Planilla, Auditoría y Usuarios
│       └── login.html            Inicio de sesión y creación del primer Administrador
├── controllers/                  CONTROLADOR: lógica de interacción
│   ├── consola_controller.py     Opciones del menú de consola
│   └── web_controller.py         Rutas de la interfaz web (Flask)
├── pruebas.py                    Casos de prueba automáticos
├── data/                         Aquí se guardan la base de datos (asistencia.db) y el Excel (se crea sola)
├── requirements.txt
└── README.md
```

**Ordenamiento:** se usa `sorted()` de Python (Timsort, O(n log n)) para ordenar trabajadores por código y asistencias por fecha. No se usan burbuja ni selección (O(n²)), porque solo sirven para proyectos pequeños. La búsqueda binaria recursiva y el conteo recursivo de tardanzas se mantienen.

### 8. Menú

| Opción | Acción |
|---|---|
| 1 | Registrar trabajador (código, nombres, DNI, cargo, turno habitual y tarifa por hora) |
| 2 | Listar trabajadores |
| 3 | Buscar trabajador por código (búsqueda binaria recursiva) |
| 4 | Marcar entrada (el turno de la jornada puede ser distinto al habitual) |
| 5 | Marcar salida y calcular las horas trabajadas |
| 6 | Ver las asistencias de un trabajador |
| 7 | Ver todas las asistencias ordenadas por fecha (ordenamiento con sorted) |
| 8 | Contar tardanzas (recursivo) |
| 9 | Generar la planilla mensual (horas por turno × tarifa por hora) |
| 10 | Exportar el reporte del mes a Excel |
| 11 | Modificar trabajador (**solo Administrador**) |
| 12 | Eliminar trabajador (**solo Administrador**) |
| 13 | Ver historial de auditoría (**solo Administrador**) |
| 14 | Crear usuario (**solo Administrador**) |
| 0 | Cerrar sesión y salir (guarda todos los datos) |

### 9. Interfaz web

Se ejecuta con `python app_web.py`, pide iniciar sesión y tiene estas pestañas:

| Pestaña | Qué permite |
|---|---|
| Trabajadores | Registrar trabajador, listar y buscar por código (búsqueda binaria recursiva) |
| Asistencia | Marcar entrada y salida (ver reglas abajo), filtrar por código, ordenar por fecha y ver el total de tardanzas (las tardanzas salen en rojo) |
| Planilla mensual | Generar la planilla de un mes (horas por turno × tarifa), ver el total y descargar el Excel |
| Auditoría (Administrador) | Ver el historial: fecha y hora, usuario, acción (Insertar, Modificar, Eliminar, Buscar...) y detalle |
| Usuarios (Administrador) | Crear usuarios y ver la lista; las contraseñas tienen un **ojito** para ver lo escrito y un aviso de si coinciden |

En la pestaña Trabajadores, el Administrador además ve los botones **Modificar** y **Eliminar** de cada fila.

Usa los mismos módulos y la misma base de datos que el menú de consola, así que ambos se pueden usar con los mismos datos. El HTML y el CSS están en `views/templates/index.html` (vista) y `controllers/web_controller.py` conecta los botones con los modelos.

**Reglas de la pantalla Asistencia (web).** Se validan siempre en el servidor (`_validar_marcacion` en `web_controller.py`); la página solo ayuda a cumplirlas (pruebas P70 a P72):

- **Hora en AM/PM.** La hora se elige con tres casillas (hora 1-12, minutos y AM/PM), viene con la hora actual y se mantiene al día mientras no se toque. Las tablas y los mensajes muestran `08:15 AM`, `04:45 PM`. Internamente se guarda en 24 h (`16:45`) para que las comparaciones y la planilla no cambien. `12:00 AM` es medianoche y `12:00 PM` mediodía.
- **Turno obligatorio.** No se marca entrada ni salida sin turno. El formulario no tiene opción vacía: propone solo el turno según la hora (antes de las 14:00 Mañana, desde las 14:00 Tarde) y la persona puede cambiarlo. Si llega una marcación sin turno o con un turno inválido, el servidor la rechaza.
- **Solo la fecha de hoy.** El campo Fecha trae la fecha actual, no se puede editar y el servidor rechaza cualquier otra (pasada, futura o con otro formato). Por eso ya no se pueden registrar ni corregir asistencias de días anteriores desde la web.
- **Exportación solo a Excel** (web y consola). Los módulos `views/reporte_csv.py` y `views/reporte_json.py` ya no se usan desde ninguna pantalla.

### 9.1 Autenticación, roles y auditoría

**Autenticación.** Los usuarios se guardan en la tabla `usuarios`. La contraseña no se guarda: se guarda un hash PBKDF2-HMAC-SHA256 con sal aleatoria y 200 000 iteraciones (`models/usuarios.py`, solo librería estándar). Reglas del **usuario**: solo letras (A-Z, sin tildes ni ñ), números y guion bajo `_`; debe empezar con una letra; de 4 a 15 caracteres; sin espacios ni símbolos (se guarda en minúsculas, así que `Juan_01` y `juan_01` son el mismo usuario). Si el usuario es inválido, el programa muestra el motivo exacto (espacios, primera letra, largo o símbolos) y no deja continuar. Reglas de la **contraseña**: de 8 a 128 caracteres con al menos una letra y un número, distinta del usuario. El mensaje de error es siempre "Usuario o contraseña incorrectos", sin decir cuál falló.

- Consola: 3 intentos y el programa se cierra. La contraseña se escribe oculta (`getpass`).
- Web: la sesión dura 8 horas, la cookie es `HttpOnly` y `SameSite=Lax`, cada formulario lleva un token CSRF, y 5 intentos fallidos seguidos bloquean a ese usuario 60 segundos dentro del proceso activo. La clave que firma la sesión se genera al azar y se guarda en `data/secret.key` (no se distribuye ni se sube a GitHub). Para HTTPS se debe activar `SESSION_COOKIE_SECURE`; en el modo local HTTP de `127.0.0.1` permanece desactivado.

**Nombre completo.** El nombre de cada usuario (también el del primer Administrador) debe ser nombres y apellidos: solo letras (con tildes y ñ), espacios, guion o apóstrofo, al menos 2 palabras y hasta 60 caracteres. Se rechazan los números (`123566`), los símbolos (`@`) y una sola palabra (prueba P61).

**Roles.** Hay dos roles: **Administrador** y **Trabajador**. Ambos inician sesión, pero con limitaciones. Los permisos están en una sola tabla (`PERMISOS_POR_ROL` en `models/usuarios.py`) y la consola y la web la consultan siempre.

| Parte del sistema | Trabajador | Administrador |
|---|---|---|
| Asistencia: marcar entrada y salida, ver asistencias y tardanzas (opciones 4 a 8) | Sí, **solo la suya** | Sí, la de **cualquier** trabajador |
| Administración de trabajadores: registrar, listar, buscar, modificar y eliminar (opciones 1, 2, 3, 11 y 12) | No | Sí |
| Reportes: planilla mensual y exportar a Excel (opciones 9 y 10) | No | Sí |
| Auditoría (opción 13) | No | Sí |
| Crear usuarios (opción 14) | No | Sí |

**Inicio de sesión.** En la interfaz web se ingresan únicamente usuario y contraseña. No existe selector de rol ni registro público. El rol real y sus permisos se consultan desde la base de datos; modificar datos enviados desde el navegador no permite convertirse en Administrador. En la consola se conserva el selector `A`/`T` como confirmación de la cuenta. La creación de cuentas posteriores se realiza desde la sección Usuarios, disponible solo para el Administrador. La primera cuenta Administrador se configura una sola vez cuando todavía no existe un Administrador. La cuenta técnica SuperAdmin es interna, no se ofrece en la interfaz y no se muestra en el listado de usuarios.

**Pantalla de inicio por rol (web).** El **Administrador** empieza en **Inicio**: trabajadores activos, asistencias de hoy, jornadas sin salida, tardanzas del mes, las últimas asistencias registradas y el botón para exportar el mes a Excel. El **Trabajador** empieza en **Marcar mi asistencia**, con su nombre, el estado de su jornada de hoy y solo su propio historial, y no puede abrir el panel ni las demás pestañas (prueba P69).

**Cuenta vinculada a un trabajador.** Una cuenta de rol Trabajador se crea **vinculada** a un trabajador registrado y activo (campo `codigo_empleado`, un trabajador solo puede tener una cuenta). Así el sistema sabe de quién es cada marcación: el Trabajador no escribe su código, no puede marcar la entrada ni la salida de otra persona (se bloquea y queda en la auditoría como «Acceso denegado») y solo ve sus propias asistencias y tardanzas. El Administrador no tiene esa restricción y marca o corrige la de cualquiera. Una cuenta de Trabajador sin vínculo (de una base anterior) no puede marcar asistencia hasta que se cree su cuenta vinculada (pruebas P62 a P66).

Cuando un Trabajador intenta entrar a una parte de administrador (escribiendo la opción en la consola o la dirección en el navegador) aparece **"No tienes permiso."** Su menú de consola y sus pestañas de la web solo muestran lo que puede usar: en la web ve únicamente la pestaña Asistencia. Las bases creadas con la versión anterior (rol "Operador") pasan a "Trabajador" automáticamente al abrirse.

**Modificar y eliminar.** Modificar aplica las mismas validaciones que registrar (el código no se puede cambiar y el DNI no puede ser el de otro trabajador). Eliminar tiene dos casos: si el trabajador **no tiene asistencias** se borra; si **ya tiene asistencias** se le da de **baja** (estado `Inactivo`), así no se pierde el historial ni quedan asistencias sin dueño. Un trabajador de baja no sale en la planilla y no puede marcar entrada.

**Auditoría.** La tabla `auditoria` guarda usuario, acción, entidad, detalle y fecha y hora. Acciones: Insertar, Modificar, Eliminar, Buscar, Exportar, Login, Logout y Login fallido. Nunca se guardan contraseñas. La base tiene triggers que impiden `UPDATE` y `DELETE` sobre esa tabla: el historial solo crece.

### 10. Reglas de negocio

- La empresa trabaja con **2 turnos**: `M` (Mañana) y `T` (Tarde).
- Hora tope de entrada por turno: **Mañana 08:00** y **Tarde 14:00**. Son valores de ejemplo configurables en `HORA_TOPE_POR_TURNO` (`models/asistencia.py`); deben confirmarse con la gerencia.
- Una entrada posterior al tope de **su turno** se registra como tardanza.
- El pago es **mensual**: horas trabajadas en el mes × tarifa por hora del trabajador.
- Formatos: código `E###` (ejemplo `E001`), DNI de 8 dígitos, fecha `AAAA-MM-DD`, hora `HH:MM`, mes `AAAA-MM`.
- Cargos válidos: Parrillero, Mesero, Caja, Cocina y Administracion.
- DNI: 8 dígitos (0-9). Se rechazan los DNI con todos los dígitos iguales (`00000000`, `11111111`), las secuencias (`12345678`, `87654321`), los patrones repetidos (`12121212`, `12341234`) y los DNI repetidos entre trabajadores.
- **Límites de los datos** (valores de ejemplo, deben confirmarse con la gerencia):
  - Tarifa por hora: mayor que 0 y hasta **S/ 500** (`MAX_TARIFA_HORA` en `models/validaciones.py`), con punto decimal y máximo 2 decimales. Se rechazan `inf`, `infinity`, `nan`, `1e999`, notación científica, comas y dígitos que no sean 0-9.
  - Horario del local: solo se aceptan marcaciones entre **06:00 y 23:00** (`HORA_APERTURA` y `HORA_CIERRE` en `models/asistencia.py`). La entrada debe ser antes de las 23:00 y la salida después de las 06:00 y hasta las 23:00.
  - La hora de salida debe ser **posterior** a la de entrada (no se acepta la misma hora).
  - Una jornada no puede durar más de **12 horas** (`MAX_HORAS_JORNADA` en `models/asistencia.py`).

### 11. Base de datos y privacidad

**Base de datos:** el sistema usa **SQLite**, un solo archivo (`data/asistencia.db`) que se crea solo la primera vez, sin instalar ni configurar ningún servidor. Tiene 4 tablas:

| Tabla | Contenido |
|---|---|
| `empleados` | codigo (clave primaria), nombres, apellidos, dni, cargo, turno, tarifa_hora, estado |
| `asistencias` | id, codigo_empleado, fecha, turno, hora_entrada, hora_salida, horas_trabajadas, tardanza, observaciones (con índice por código y fecha) |
| `usuarios` | usuario (clave primaria), nombre, rol, clave_hash, creado, codigo_empleado (trabajador vinculado) |
| `auditoria` | id, usuario, accion, entidad, detalle, fecha_hora (solo se agrega, no se edita ni se borra) |

Las tablas nuevas se crean solas al abrir una base existente: no hay que migrar nada a mano.

`models/base_datos.py` es el único archivo que habla con la base; el resto del programa sigue trabajando con listas de diccionarios. Cada guardado es una transacción: si algo falla (por ejemplo un código repetido), la base queda como estaba. Si existen los CSV de versiones anteriores (`data/empleados.csv` y `data/asistencias.csv`), sus datos se importan solos la primera vez que se crea la base.

Los archivos de la carpeta `data/` contienen datos personales (DNI, horarios y tarifas), protegidos por la Ley N.° 29733 (Protección de Datos Personales). Por eso el `.gitignore` **no sube** los `.db`, `.csv`, `.xlsx`, `.json` ni la clave `secret.key` a GitHub. Los reportes exportados (Excel) se guardan en `data/`. Si el Excel está abierto, el programa avisa y no se cierra: hay que cerrarlo y volver a exportar.

**Codificación UTF-8:** todo el proyecto usa UTF-8 (código con la cabecera `# -*- coding: utf-8 -*-`, base de datos SQLite y página web), por lo que se aceptan tildes, ñ, ü, ç y cualquier letra en nombres y apellidos. Los CSV antiguos se importan con o sin BOM.

**Portabilidad:** no hay rutas fijas, por lo que el proyecto corre en otra computadora con solo Python, openpyxl y flask. Como `data/` no se sube a GitHub, para llevar los datos hay que copiar el archivo `data/asistencia.db` a mano.

**Seguridad contra inyección SQL:** (1) todo dato que escribe el usuario viaja a SQLite como *parámetro* (`?`), nunca se concatena dentro del texto SQL, así que un texto como `'; DROP TABLE empleados; --` se trata solo como dato; (2) los nombres de tabla y de columnas no vienen del usuario: salen de constantes y se verifican contra una lista blanca (`TABLAS_PERMITIDAS` en `models/base_datos.py`); (3) además, la validación rechaza los datos con formato inválido antes de llegar a la base. Lo comprueban las pruebas P41 y P42.

### 12. Temas del curso que usamos

if, while, funciones, módulos, listas de diccionarios, base de datos SQLite (sqlite3), manejo de archivos (Excel, CSV y JSON), hash de contraseñas con hashlib, try/except, recursividad, ordenamiento con sorted(), arquitectura MVC. Como extra, una interfaz web con Flask y HTML, autenticación con roles y auditoría.

### 13. Trabajo con Git

Cada integrante trabaja en su propia rama (`feature/validaciones`, `feature/empleados`, `feature/asistencia`, `feature/persistencia-reportes`, `feature/main-integracion`) y la une a `main` con un Pull Request.

Ramas sugeridas para lo nuevo: `feature/autenticacion` (models/usuarios.py, login de consola y web), `feature/auditoria` (models/auditoria.py y su vista) y `feature/exportaciones` (views/reporte_csv.py y reporte_json.py). Las versiones se marcan con etiquetas:

```
git tag -a v1.0 -m "Version de consola con SQLite y Excel"
git tag -a v1.1 -m "Interfaz web, exportacion CSV y JSON"
git tag -a v1.2 -m "Autenticacion, roles, auditoria y CRUD de trabajadores"
git push origin --tags
```

### 14. Limitaciones

Los límites de tarifa, horario y duración de la jornada son valores de ejemplo por confirmar con la gerencia. Los usuarios no se pueden desactivar ni cambiar de contraseña desde el programa (solo crear); un trabajador dado de baja no se puede reactivar desde el programa; la web corre en una sola computadora (un usuario a la vez, porque SQLite es un archivo local y no un servidor de base de datos); la hora la digita una persona; la web usa HTTP local (127.0.0.1), por lo que si se publica en una red hay que ponerla detrás de HTTPS; no se contemplan turnos que cruzan la medianoche, horas extra, feriados ni la sucursal de cada trabajador.