import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

def get_db_connection():
    try:
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