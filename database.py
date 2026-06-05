import pg8000
import streamlit as st

def get_db_connection():
    try:
        # Si está en la nube, usa los Secrets de AWS con pg8000
        if "DB_HOST" in st.secrets:
            return pg8000.connect(
                host=st.secrets["DB_HOST"],
                database=st.secrets["DB_NAME"],
                user=st.secrets["DB_USER"],
                password=st.secrets["DB_PASSWORD"],
                port=int(st.secrets["DB_PORT"]),  # pg8000 pide el puerto como número entero
                timeout=5
            )
        
        # Entorno local (puedes dejarlo con psycopg2 o cambiarlo también, pero para probar la nube usemos pg8000)
        return pg8000.connect(
            host="localhost",
            database="petskin_db",
            user="postgres",
            password="Farjevasquez16*",
            port=5432,
            timeout=3
        )
    except Exception as e:
        # Capturamos cualquier error para que nos avise
        st.error(f"❌ Error de conexión detallado: {e}")
        st.stop()
