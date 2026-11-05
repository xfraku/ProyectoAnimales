# Actualización de PetSkin AI

El código utiliza Streamlit, PostgreSQL en RDS y fotografías privadas en S3. Conserva las cuentas, las contraseñas existentes y los modelos originales.

## 1. Actualizar la base existente

Sigue la [guía de pgAdmin](PGADMIN.md) y ejecuta `migrations/001_pgadmin.sql` sobre `petskin_db`, después de respaldarla. Si ya obtuviste `actualizacion_aplicada = true`, este paso está completado.

No es necesario recrear RDS o S3 ni ejecutar instaladores de CloudShell. Las nuevas fotos de perfil se guardan en `consultas/mascotas/`, dentro de los permisos originales del bucket.

## 2. Subir el código a GitHub

Sube todos los archivos de la aplicación, especialmente los módulos nuevos, `requirements.txt`, `TERMS.md`, `assets/fonts/`, `certs/`, `.streamlit/config.toml` y `migrations/`. Mantén `modelo_PRO_perritos_v2.keras` en el repositorio. La documentación y las pruebas también pueden subirse.

No subas `.venv/`, `test-output/`, `ApiKey.txt`, `.streamlit/secrets.toml`, respaldos ni archivos privados de AWS. Están excluidos por `.gitignore`. Si Git ya tenía una contraseña en su historial, quitarla del archivo actual no borra ese historial; cambia esa contraseña si todavía se usa.

En Streamlit Community Cloud, la entrada sigue siendo `app.py`. Reinicia la app para que instale las dependencias nuevas. Si permite seleccionar la versión de Python, utiliza una compatible con TensorFlow 2.21 (se verificó Python 3.13 en las pruebas locales).

## 3. Secrets

Conserva los valores actuales de:

```text
DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET_NAME, AWS_REGION
OPENAI_API_KEY
```

`DB_USER` debe ser `petskin_app`, el usuario de aplicación creado previamente. La conexión remota verifica TLS usando `certs/us-east-2-bundle.pem`; no se conecta sin verificar el certificado.

El destinatario ya viene configurado por defecto. Si quieres dejarlo explícito, añade en Secrets:

```toml
TEAMS_CONTACT_EMAIL = "gufa978@gmail.com"
```

El botón abre una llamada de Teams. La dirección debe corresponder a una identidad a la que la cuenta de Teams del usuario pueda llamar; conocer un Gmail por sí solo no garantiza esa compatibilidad. Prueba la llamada con el destinatario. Si su cuenta no permite la llamada directa, crea una reunión real de Teams y añade su enlace:

```toml
TEAMS_MEETING_URL = "PEGA_AQUI_EL_ENLACE_HTTPS_REAL_DE_TEAMS"
```

Reemplaza todo el valor por el enlace real antes de guardarlo. Si existe esta opción, el botón abre esa reunión. No es necesario modificar código.

Los modelos de OpenAI por defecto siguen siendo `gpt-4o-mini`. Se pueden configurar con `VISION_MODEL` y `CHAT_MODEL`; cualquier sustitución debe admitir imágenes (para visión) y salidas JSON estructuradas. La validación agrega una llamada de IA por análisis y consume el saldo de OpenAI, independiente de los créditos de AWS.

## 4. Verificación después de publicar

1. Inicia sesión con tu administrador existente. Las cuentas anteriores aceptan los términos una vez; no se inventa una aceptación histórica.
2. Crea una cuenta de prueba, intenta duplicar su usuario y correo, y verifica que se rechacen.
3. Registra una mascota desde **Mis mascotas**. Confirma que no admita nombre/raza vacíos ni 4000 kg.
4. Desde **Nueva consulta**, selecciona la mascota y una fotografía canina real. Pulsa **Analizar fotografía**. Esto confirma la conexión real a OpenAI, la carga del modelo y la escritura/lectura de S3.
5. Sube una foto de un objeto, un archivo dañado y una imagen demasiado pequeña. Comprueba mensajes claros y que no se creen consultas. Para el filtro semántico usa varias fotos: es un control de IA, no una garantía de detección perfecta.
6. Consulta los resultados, abre **Ver reporte PDF**, descarga y comprueba la imagen, acentos y datos. Envía dos preguntas, actualiza el resumen y vuelve a descargar.
7. Abre **Llamar veterinario ahora** y confirma con el destinatario que la llamada o reunión es accesible. Esto no se probó llamándolo automáticamente.
8. Prueba cancelar y confirmar una eliminación, editar el correo, asignar especialista, suspender/reactivar y cambiar la contraseña. Mantén al menos un administrador activo.
9. En otra sesión, falla cinco veces la contraseña de la cuenta de prueba. Verifica bloqueo de una hora y el evento de acceso en el panel administrativo. Si la plataforma no proporciona una IP, aparecerá vacía: no se inventa.
10. En **Métricas y auditoría**, abre el gráfico, registra una observación y procesa los archivos pendientes de eliminación. Comprueba que no haya errores de permisos.

Revisa y aprueba el texto de `TERMS.md` y los consejos preventivos con el responsable del aplicativo y el veterinario antes de ofrecer el servicio. El texto describe la funcionalidad implementada; no constituye una certificación jurídica ni clínica.

## Respaldo y recuperación

La migración añade columnas y tablas; no elimina las cuatro tablas originales. Los datos antiguos de mascotas se copian a las consultas con la marca **“Datos disponibles al migrar”**, porque no es posible reconstruir cambios históricos anteriores.

Si necesitas volver al código anterior, conserva las columnas nuevas; no hace falta eliminarlas. No ejecutes `pg_restore --clean` sobre producción como primera medida. El respaldo entregado puede restaurarse primero en una base separada para revisar datos. La guía no ejecuta ninguna restauración destructiva.

## Documentación técnica consultada

- [Streamlit: visor de PDF y dependencia adicional](https://docs.streamlit.io/1.56.0/develop/api-reference/media/st.pdf).
- [OpenAI: imágenes y visión](https://developers.openai.com/api/docs/guides/images-vision).
- [OpenAI: salidas estructuradas](https://developers.openai.com/api/docs/guides/structured-outputs).
