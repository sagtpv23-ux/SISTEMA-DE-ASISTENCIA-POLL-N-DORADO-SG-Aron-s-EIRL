# Revisión de seguridad, validaciones y límites

## Cambios aplicados en esta corrección

- El login web solicita únicamente usuario y contraseña. No presenta registro público ni selector de rol.
- Los permisos se resuelven en el servidor a partir del usuario autenticado en SQLite.
- La creación de cuentas posteriores queda dentro del módulo Usuarios, protegido para Administrador.
- La configuración inicial permite crear el primer Administrador solo cuando no existe ninguna cuenta.
- Los campos de usuario, contraseña y nombre tienen límites HTML de longitud y ayudas de entrada; las reglas reales siguen validándose en el modelo.
- La clave de firma de sesión ya no cae silenciosamente a una clave temporal si no puede guardarse. Se detiene con un error claro. Se puede definir `SG_ARONS_SECRET_KEY` (mínimo 32 caracteres) en el entorno.
- Se limita el tamaño de los formularios HTTP, se agregan cabeceras de seguridad y se acota el número de iteraciones PBKDF2 aceptado al verificar hashes guardados.
- `.gitignore` excluye bases de datos, reportes, secretos, entornos virtuales y cachés.

## Hallazgos y riesgos que siguen requiriendo atención

1. **Bloqueo de login en memoria:** los 5 intentos/60 segundos se guardan en un diccionario del proceso. Reiniciar el servidor o ejecutar varios procesos puede reiniciar o eludir el bloqueo. Para producción, guardar el contador y el vencimiento en SQLite con transacciones o usar un limitador persistente por IP y cuenta.
2. **Datos en memoria:** empleados y asistencias se cargan al iniciar y se guardan como listas completas. No es adecuado para varios usuarios concurrentes ni varios procesos. Un fallo de guardado puede dejar temporalmente la memoria distinta de SQLite. Antes de uso multiusuario, migrar las operaciones a consultas transaccionales directas y actualizar la interfaz solo después de confirmar el commit.
3. **SQLite y copias de seguridad:** el archivo es un punto único de fallo. Hacer copias periódicas, probar restauración y no copiar la base mientras está siendo escrita sin usar la API de backup de SQLite.
4. **Auditoría:** los triggers evitan UPDATE/DELETE normales, pero alguien con acceso al archivo SQLite puede eliminar triggers o editar el archivo. No es una auditoría inviolable ni evidencia forense.
5. **Secreto de sesión:** proteger `data/secret.key` con permisos del sistema operativo y respaldarlo de forma segura. Si se pierde o cambia, las sesiones existentes dejan de ser válidas. No compartirlo ni incluirlo en ZIP/Git.
6. **Transporte:** HTTP solo es aceptable para uso local en `127.0.0.1`. No exponer el puerto a una LAN o Internet. Para red, usar HTTPS, servidor WSGI de producción, firewall y `SESSION_COOKIE_SECURE=True`.
7. **Datos personales:** DNI, asistencia y tarifas son datos sensibles para la operación. Restringir el acceso al equipo, cifrar disco/copias y definir retención, consentimiento/base legal y procedimiento de atención conforme a la normativa peruana de protección de datos.
8. **Validación de negocio:** confirmar con la empresa topes de entrada, horario 06:00–23:00, máximo 12 horas y tarifa máxima S/ 500. Son reglas configurables de ejemplo, no reglas legales universales.
9. **Integridad de asistencia:** el sistema no contempla turnos que crucen medianoche, varias jornadas del mismo turno por día, feriados, horas extra, cambios de tarifa históricos ni correcciones con doble aprobación. Esos casos pueden afectar el cálculo de planilla.
10. **Caídas:** proteger contra disco lleno, archivo DB bloqueado/dañado, falta de permisos y cierre abrupto. Mantener backups, registrar errores técnicos sin contraseñas y probar recuperación.
11. **Exportaciones:** los archivos descargados contienen DNI, horarios y pagos. Deben guardarse en ubicaciones controladas y eliminarse de forma segura cuando ya no sean necesarios.
12. **Despliegue:** el servidor de desarrollo de Flask no es para producción. `debug=False` debe mantenerse; usar un WSGI server y un proxy HTTPS si se publica.

## Validaciones revisadas

- Usuario: 4–15 caracteres, inicia con letra, letras ASCII, números y `_`.
- Contraseña: 8–128 caracteres, al menos una letra y un número; hash PBKDF2-HMAC-SHA256 con sal aleatoria.
- Nombre: nombres y apellidos, caracteres de letras Unicode, espacios/guion/apóstrofo; máximo 60.
- DNI: 8 dígitos y reglas adicionales anti-patrones; estas reglas heurísticas no verifican la titularidad del DNI.
- Código de trabajador: E seguido de 3 dígitos.
- Tarifa: mayor que cero, máximo S/ 500, hasta 2 decimales.
- Fecha/hora/mes: formato estricto y fecha real; salida posterior a entrada.
- Turno/cargo: valores de lista permitida.
- CSRF: todos los POST deben incluir token de sesión.
- SQL: los valores se pasan como parámetros SQLite `?`; los identificadores dinámicos se restringen mediante lista blanca.
- XSS: las plantillas Jinja escapan automáticamente los valores; no introducir `|safe` para datos de usuarios.

## Ejecución de pruebas

Ejecutar desde la carpeta del proyecto:

```bash
pip install -r requirements.txt
python -m compileall .
python pruebas.py
```

Las pruebas web requieren Flask instalado. La suite existente se actualizó en P67 para reflejar el login web de usuario/contraseña sin selector de rol.

## Refuerzo adicional aplicado (segunda revisión)

- SQLite: `busy_timeout` de 5 s, `foreign_keys=ON`, `trusted_schema=OFF`, modo WAL y límites del motor para longitud de SQL/datos/columnas.
- Asistencia web: el servidor exige turno válido, hora válida (12 h con AM/PM o 24 h) y que la fecha sea la de hoy; no se confía en el formulario HTML (`readonly`, `min`/`max`, selectores).
- Exportación: solo Excel. Se retiraron las rutas y botones de CSV/JSON; cualquier otro `formato` se rechaza.
- Ojito de contraseña: es solo del lado del navegador (cambia el tipo del campo entre `password` y `text`); la contraseña no se envía ni se guarda en ningún momento por usarlo. Recordar que mostrarla en pantalla compartida la expone.
- Login web: comprobación de longitud del usuario y contraseña en servidor antes de invocar PBKDF2; no se confía en las validaciones HTML.
- La protección SQL existente se conserva: valores mediante parámetros `?` y los identificadores dinámicos solo mediante lista blanca. No se deben cambiar estas reglas por concatenación de datos de formulario.

## Verificación en este entorno

- `python -m compileall .`: correcto.
- Suite `pruebas.py`: 61/69 casos ejecutados correctamente; los 8 casos web no pudieron ejecutarse porque Flask no está instalado y el entorno no tuvo acceso a Internet para instalarlo. Los casos P41 y P42 de inyección SQL se ejecutaron y aprobaron (88 entradas maliciosas rechazadas por validación y prueba de parametrización/lista blanca).
- Antes de usar o entregar: instalar `pip install -r requirements.txt` y volver a ejecutar la suite completa en una computadora con Flask disponible.

## Ajustes solicitados en la pantalla de autenticación (26-11-2026)

- La primera configuración identifica al Administrador inicial como **SuperAdmin** en la interfaz; la base mantiene el rol `Administrador` para compatibilidad con los permisos actuales.
- En la configuración inicial, el nombre completo exige exactamente dos palabras (nombre y apellido), con un mínimo de dos letras por palabra. Se rechazan iniciales sueltas como `A A`, una sola palabra, tres o más palabras, números y símbolos.
- La validación del nombre se realiza en el navegador para dar retroalimentación inmediata y también en el modelo del servidor para que no pueda eludirse.
- La contraseña de creación requiere al menos 8 caracteres, letras y números. La contraseña y su repetición se validan antes del envío.
- Se agregaron botones de mostrar/ocultar contraseña (ojo) a los campos de contraseña.
- El login de cuentas existentes contiene solamente usuario y contraseña; no permite seleccionar el rol desde el navegador.
- La pantalla se actualizó con estilo azul inspirado en la referencia visual enviada.
