# PetSkin AI

Asistente de orientación dermatológica canina con Streamlit, un clasificador Keras, OpenAI, PostgreSQL en RDS y fotografías privadas en S3.

## Actualización acordada

- [Actualización de base de datos y publicación](docs/DESPLIEGUE.md)
- [Cobertura de las 18 incidencias y 22 casos de prueba visibles](docs/COBERTURA_Y_PRUEBAS.md)
- [Términos de uso](TERMS.md)
- [Ejemplo de Secrets sin credenciales reales](.streamlit/secrets.toml.example)

La entrada sigue siendo `app.py`. Instala `requirements.txt` y ejecuta `streamlit run app.py`. Aplica la migración antes de publicar la nueva versión. No subas credenciales a GitHub.

El especialista accede a sus propios pacientes, igual que un usuario. El administrador gestiona cuentas, roles, acceso, consejos preventivos y auditoría. El resultado por debajo del 60 % se presenta como no concluyente. La confianza no equivale a exactitud clínica.

El filtro de pertinencia de imágenes utiliza visión de OpenAI; no se reentrenó ni se modificó el clasificador original. La API key se conserva. Las imágenes se almacenan de forma privada y los PDF incluyen la consulta completa.
