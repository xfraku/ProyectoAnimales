import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

def get_db_connection():
    try:
        # 1. Si la app está en la nube de Streamlit, detectará "DB_HOST" en los Secrets y usará AWS
        if "DB_HOST" in st.secrets:
            return psycopg2.connect(
                host=st.secrets["DB_HOST"],
                database=st.secrets["DB_NAME"],
                user=st.secrets["DB_USER"],
                password=st.secrets["DB_PASSWORD"],
                port=st.secrets["DB_PORT"],
                connect_timeout=3
            )
        
        # 2. Si estás corriendo el proyecto en tu PC local, pasará de largo y usará tu localhost de siempre
        return psycopg2.connect(
            host="localhost",
            database="petskin_db",
            user="postgres",
            password="Farjevasquez16*",
            port="5432",
            connect_timeout=3
        )
    except psycopg2.OperationalError:
        st.error("❌ Error de conexión a PostgreSQL.")
        st.stop()
