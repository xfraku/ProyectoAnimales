# Actualizar la base existente desde pgAdmin

Esta guía actualiza la base existente. Ejecuta únicamente `migrations/001_pgadmin.sql` en `petskin_db`; no ejecutes `000_baseline.sql`, que está destinado a una base vacía.

## 1. Permitir la conexión desde tu computadora

En AWS abre **RDS → Databases → petskin-postgres → Connectivity & security**. Comprueba que **Publicly accessible** indique **Yes**, como en la configuración inicial para Streamlit. Si indica No, no basta abrir una regla: se necesita una conexión mediante la red privada; no cambies esa configuración a ciegas.

Abre el **VPC security group** asociado. En **Inbound rules → Edit inbound rules**, añade una regla:

- Tipo: **PostgreSQL**.
- Puerto: **5432**.
- Origen: **My IP / Mi IP**, que debe terminar en `/32`.

Conserva las reglas existentes que usa Streamlit. No uses `0.0.0.0/0`. Cuando termines, puedes retirar solo la regla que agregaste para tu computadora.

## 2. Conectar pgAdmin

Abre pgAdmin 4 en tu computadora. Si no está instalado, obtén el instalador en https://www.pgadmin.org/download/pgadmin-4-windows/ . No necesitas instalar otro servidor PostgreSQL.

Haz clic derecho en **Servers → Register → Server**.

En **General**, nombre: `PetSkin RDS`.

En **Connection**:

| Campo | Valor |
|---|---|
| Host name/address | El endpoint actual de RDS, igual al valor de `DB_HOST` en tus Secrets; sin `https://` ni puerto añadido. |
| Port | `5432` |
| Maintenance database | `petskin_db` |
| Username | `postgres` |
| Password | La contraseña del administrador de RDS del ZIP privado original. No es la contraseña del administrador de la aplicación ni necesariamente `DB_PASSWORD` (que corresponde a `petskin_app`). |

Consulta la contraseña del administrador en tu respaldo privado de credenciales, fuera del repositorio. No copies las claves al chat.

En **Parameters** (o **SSL**, según la versión de pgAdmin):

- `SSL mode`: `verify-full`.
- `Root certificate`: selecciona `us-east-2-bundle.pem`, incluido en la carpeta de esta entrega.

Guarda la conexión. Referencias: [conexión de pgAdmin a RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ConnectToPostgreSQLInstance.pgAdmin.html) y [parámetros de conexión de pgAdmin](https://www.pgadmin.org/docs/pgadmin4/latest/server_dialog.html).

## 3. Respaldar y ejecutar

1. Expande **PetSkin RDS → Databases → petskin_db**.
2. Clic derecho en **petskin_db → Backup**, selecciona formato **Custom** y guarda el respaldo en tu computadora. Si pgAdmin indica que su `pg_dump` es anterior al servidor, actualiza pgAdmin o sus herramientas PostgreSQL; no continúes sin un respaldo verificable. También puedes crear un snapshot manual de la instancia RDS desde AWS, teniendo en cuenta el almacenamiento del respaldo.
3. Clic derecho en **petskin_db → Query Tool**.
4. Abre `migrations/001_pgadmin.sql` con el icono de abrir archivo. Sin seleccionar un fragmento, ejecuta el archivo completo mediante **Execute script / F5**.
5. Espera a que finalice sin errores. La última consulta muestra `actualizacion_aplicada = true`.

El archivo incluye una transacción, tiempos máximos de espera y una comprobación de que estás conectado a `petskin_db`. Añade columnas/tablas/permisos y conserva los registros y contraseñas existentes. Es repetible. Si se produce un error, ejecuta `ROLLBACK;` en esa pestaña antes de corregirlo y volver a intentar.

La consulta final confirma la versión aplicada sin mostrar contraseñas.

## 4. Publicar

Sube a GitHub el código actualizado de esta misma entrega y reinicia Streamlit. Conserva tus Secrets actuales, incluida la API key. Las nuevas fotografías se guardan dentro de `consultas/*`, por lo que mantienen compatibilidad con la política S3 original: no necesitas modificar IAM para esta actualización.

Comprueba una consulta real con foto, chat, PDF y WhatsApp. La aplicación usa el mismo RDS, bucket y cuentas; las funciones nuevas requieren las columnas/tablas añadidas por este SQL.
