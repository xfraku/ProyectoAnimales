import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

def get_db_connection():
    try:
        if "DB_HOST" in st.secrets:
            return psycopg2.connect(
                host=st.secrets["DB_HOST"],
                database=st.secrets["DB_NAME"],
                user=st.secrets["DB_USER"],
                password=st.secrets["DB_PASSWORD"],
                port=st.secrets["DB_PORT"],
                connect_timeout=5
            )
        
        return psycopg2.connect(
            host="localhost",
            database="petskin_db",
            user="postgres",
            password="Farjevasquez16*",
            port="5432",
            connect_timeout=3
        )
    except psycopg2.OperationalError as e:
        # Aquí capturamos la queja real de PostgreSQL y la mostramos en la web
        st.error(f"❌ Error de conexión detallado: {e}")
        st.stop()
