# Cobertura y pruebas de PetSkin AI

## Alcance documental

Se contrastaron `Correcciones Mantis.pdf`, la captura con las 18 incidencias, la hoja **Historia de Usuario V4.0 (2)** y los casos visibles de **LISTA CP / CP_1 a CP_22**. No se utilizaron hojas, filas ni columnas ocultas como requisitos. En particular, las filas ocultas 17 y 18 de la hoja oficial de HU no se usaron para justificar funcionalidades. El especialista se implementa por el acuerdo explícito del usuario y los casos de prueba visibles.

Los archivos fuente son `P20252051_PROYECTO_HU.xlsx` y `P20252051_PROYECTO_CP (1).xlsx`, proporcionados por el usuario. No se modificaron esos documentos ni se cerraron incidencias en Mantis.

## Incidencias

“Implementada” indica que el cambio existe en código y fue contrastado localmente. La aceptación final en el despliegue requiere las comprobaciones de `DESPLIEGUE.md`.

| Mantis | Cambio realizado | Evidencia local / límite |
|---|---|---|
| 2798 | Historial con ID único, mascota, fecha completa, hora y resultado en español. | Navegador y pruebas de consulta/historial. |
| 2797 | Confirmación antes de eliminar consulta y mensajes. | Cancelar conserva los datos; confirmar elimina. |
| 2725 | Umbral del 60 %: por debajo se muestra “Resultado no concluyente”; se oculta la clase ganadora en contexto nuevo de IA y PDF. | Casos 59,999 % y 60 %, PDF y contexto de chat. No equivale a exactitud clínica. |
| 2720 | Validación de formato de correo en registro y edición. | Ocho formatos inválidos, vacío, normalización. No verifica existencia del buzón. |
| 2455 | Botón visible “Llamar veterinario por WhatsApp” dirigido al número de atención configurado. | URL y botón comprobados. Falta llamada real con el destinatario. |
| 2454 | Mismo flujo de confirmación que 2797, también desde el historial. | Prueba de cancelar y confirmar. |
| 2451 | Términos accesibles en Crear cuenta y al pie de las vistas autenticadas; aceptación registrada. | Por el ajuste solicitado, no se muestra el bloque de términos en Iniciar sesión. Se conserva la lógica de aceptación. |
| 2450 | Correo único sin diferencias por mayúsculas/espacios; índice en PostgreSQL y error específico. | Registro duplicado y dos registros simultáneos. |
| 2448 | Cinco errores consecutivos bloquean nuevos accesos por una hora; contador y eventos persistidos. | Concurrencia, contraseña correcta durante bloqueo, expiración y reinicio. |
| 2417 | Categorías traducidas, incluida Tiña. | Resultado, historial, gráfico, contexto nuevo de chat y PDF. No se reescriben mensajes históricos de la versión anterior. |
| 2286 | PDF desde el análisis, botón de descarga y visor integrado; imagen privada, ficha y transcripción completa. | Descarga real desde Chromium, PDF multipágina, acentos, imagen y aviso legal. |
| 2285 | Peso entre 0,1 y 120 kg en interfaz y servicio. | Rechazo de 4000, cero, negativo, texto, infinito y NaN. |
| 2284 | Nombre y raza obligatorios; se permite indicar Mestizo o Desconocida. | Validación de blancos y datos de mascotas antiguas antes de nueva consulta. |
| 2283 | Rol Especialista asignable por administrador. Tiene las mismas funciones de usuario sobre sus propios pacientes. | Permisos, transición a administrador, sesión revocada al cambiar rol. No es una certificación profesional. |
| 2282 | Suspender y Reactivar separados de Eliminar cuenta; estado Inhabilitado. | Acceso rechazado e invalidación de sesiones abiertas. |
| 2281 | Búsqueda por usuario/correo y tabla descendente. | Filtro sin sensibilidad a mayúsculas y tratamiento literal de `%`/`_`. |
| 2280 | Validación de archivo, decodificación RGB, tamaño/resolución y filtro de pertinencia con visión antes del modelo. | Archivos inválidos y respuestas de API apta/no pertinente/incierta/error simuladas. No se reentrena. La calidad semántica requiere evaluación con fotos reales y la API del despliegue. |
| 2279 | Mis mascotas permite registrar y editar pacientes antes del análisis. | Servicios, AppTest y navegación real. |

Además se elimina la creación innecesaria de `img_consultas`, origen del `FileExistsError`. El almacenamiento se realiza en S3; la aplicación no necesita crear esa carpeta al iniciar.

## Casos de prueba visibles

| Caso | Funcionalidad y comprobación |
|---|---|
| CP001 | Registro, contraseña cifrada con bcrypt, consentimiento y confirmación. |
| CP002 | Rechazo de correo duplicado, incluso en concurrencia. |
| CP003 | Rechazo de usuario duplicado. |
| CP004 | Correo obligatorio; no se inserta una cuenta incompleta. |
| CP005 | Registro de mascota, campos clínicos, fotografía opcional de perfil y vinculación de la imagen analizada a la consulta. |
| CP006 | Edición administrativa de usuario/correo con confirmación y mensaje de éxito. |
| CP007 | Búsqueda y visualización del perfil en tabla/acordeón. |
| CP008 | Eliminar cuenta revoca acceso; Suspender conserva datos como pide HU0004-2. Ambas acciones tienen confirmación. |
| CP009 | Selector de archivos comprobado en navegador; opción de cámara implementada. Captura física pendiente en el dispositivo del usuario. |
| CP010 | JPG/JPEG/PNG únicamente, comprobación del contenido real y mensaje legible para archivo dañado. |
| CP011 | Límite de 20 MB en Streamlit y validación del servicio. |
| CP012 | Cambio de rol y actualización efectiva de permisos; invalida sesiones anteriores. |
| CP013 | Especialista puede suspenderse o eliminarse y pierde acceso. |
| CP014 | Aviso solicitado presente en el PDF, con pie de página y cierre del documento. |
| CP015 | Chat con contexto clínico e historial; orientación general, manejo de fallos y almacenamiento de intercambio completo. Respuestas clínicas reales pendientes de evaluación. |
| CP016 | Asignación de Administrador a Especialista y acceso a gestión. |
| CP017 | Tabla descendente de usuarios (LISTA CP) y recuperación de foto/resultado del historial (hoja CP_17): se implementaron ambos. |
| CP018 | Gráfico por categoría, total de consultas y cantidad valorada como útil. Solo administradores. |
| CP019 | Distribución por raza/color y registro de evidencia/acción recomendada. Solo administradores; no afirma detectar sesgo automáticamente. |
| CP020 | Mensaje de credenciales inválidas; bloqueo de una hora tras cinco fallos. |
| CP021 | Alerta roja ante respuesta de IA marcada urgente, persistida y acompañada del botón de WhatsApp. Probada con respuesta controlada; no valida sensibilidad clínica real. |
| CP022 | PDF disponible al finalizar el análisis, visor, descarga y resumen actualizable de toda la conversación. |

También se cubren HU0003-2 (cambio seguro de contraseña con confirmación), HU0007-1 (consejos preventivos administrables), HU00010 (valoraciones útiles), HU00011 (eventos de acceso) y HU00012 (evidencia de auditoría).

## Diferencias que debe reflejar el procedimiento de QA

- CP005 y CP022 describen el flujo antiguo de cargar una foto y después registrar la mascota. Ahora se registra/selecciona primero la mascota, conforme a Mantis 2279. Las consultas antiguas sin mascota permiten vincular una. Se mantiene el resultado funcional, con pasos y algunos rótulos actualizados.
- CP008 y CP013 se titulan “inhabilitar”, pero sus pasos piden eliminar. Por eso se ofrecen las dos acciones, distinguiendo su efecto y solicitando confirmación.
- CP017 tiene resultados distintos en LISTA CP y CP_17. Se implementaron tanto la tabla de usuarios como el historial clínico.
- CP018 y CP019 usan el nombre de prueba `franco`, pero sus criterios/HU exigen administrador: ese usuario de QA debe tener ese rol para ejecutar esos escenarios. No se entregan estadísticas globales a usuarios comunes.
- No se proporcionó `imagenprueba.jpg`. No puede certificarse que esa fotografía produzca Dermatitis; tampoco debe forzarse esa categoría para pasar CP022. La prueba del modelo real confirma carga e inferencia, no exactitud diagnóstica.
- Los casos antiguos no contienen el paso nuevo de aceptar los términos. Debe añadirse al registro y al primer acceso de cuentas migradas.
- Los mensajes de archivo inválido/sobredimensionado pueden provenir también del control nativo de Streamlit, antes de que Python reciba el archivo. La aplicación añade instrucciones en español y valida nuevamente los archivos recibidos.

## Qué se prueba y qué no

Resultado de la ejecución local previa a la limpieza del repositorio: **60 pruebas aprobadas**, sin fallos. Cobertura de líneas de los módulos de reglas, servicios, IA, almacenamiento, PDF y conexión: **85 %**; no es un porcentaje de cumplimiento funcional ni de precisión del modelo. Se ejecutó además el recorrido de navegador Chromium en escritorio (1440 × 1000) y móvil (390 × 844), con descarga PDF. Los PDF multipágina se inspeccionaron renderizados con Poppler.

Las pruebas usan PostgreSQL 17 local, la aplicación real y servicios S3/OpenAI controlados cuando se necesitan respuestas reproducibles. El modelo Keras original se cargó y ejecutó por separado con una imagen sintética: esto verifica compatibilidad, no rendimiento clínico. No se utilizó ninguna API key privada de OpenAI ni se llamó al veterinario.

Las pruebas automatizadas no modificaron RDS, IAM o S3 de producción. Tras esa ejecución se retiraron del repositorio los auxiliares de CloudShell y sus pruebas específicas; la actualización de la base se documenta mediante pgAdmin. El recuento anterior corresponde a la suite completa de esa ejecución, no al número de pruebas restante. La vista previa y descarga PDF se probaron en Chromium; no se certifican aquí todos los navegadores/dispositivos posibles.

El cierre definitivo de las incidencias debe hacerse después de ejecutar la actualización, publicar y completar el apartado de verificación de `DESPLIEGUE.md`. Las pruebas reducen regresiones; no garantizan que nunca aparezcan incidencias nuevas.

## Repetir pruebas locales

Necesitas una base PostgreSQL **exclusiva para pruebas**, llamada `petskin_test`, escuchando solo en `127.0.0.1`, puerto `55439` (o el indicado en `PETSKIN_TEST_PORT`). Nunca configures esos tests contra RDS.

Ejecuta en esa base el esquema `migrations/000_baseline.sql` sustituyendo únicamente la comprobación de nombre `petskin_db` por `petskin_test`. Luego ejecuta `migrations/001_mantis.sql`. Instala `requirements-dev.txt` en un entorno virtual y ejecuta:

```powershell
$env:PETSKIN_TEST_DB='petskin_test'
python -m pytest -q
```

Las pruebas de integración limpian los datos de esa base local en cada escenario. Sin esa variable, se omiten para evitar tocar una base por accidente. El arnés `tests/ui_harness.py` solo arranca con `PETSKIN_UI_TEST=1`, `DB_HOST=127.0.0.1` y `DB_NAME=petskin_test`; no debe desplegarse como aplicación pública.
