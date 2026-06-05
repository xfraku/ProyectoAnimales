import pg8000.dbapi
import streamlit as st

def get_db_connection():
    try:
        if "DB_HOST" in st.secrets:
            # Creamos la conexión a AWS
            conn = pg8000.dbapi.connect(
                host=st.secrets["DB_HOST"],
                database=st.secrets["DB_NAME"],
                user=st.secrets["DB_USER"],
                password=st.secrets["DB_PASSWORD"],
                port=int(st.secrets["DB_PORT"]),
                timeout=5
            )
        else:
            # Creamos la conexión Local
            conn = pg8000.dbapi.connect(
                host="localhost",
                database="petskin_db",
                user="postgres",
                password="Farjevasquez16*",
                port=5432,
                timeout=3
            )
        
        # 🔥 EL TRUCO CORREGIDO: Activa el modo diccionario nativo para pg8000
        conn.run_mapper = pg8000.dbapi.dict_row_mapper
        return conn

    except Exception as e:
        st.error(f"❌ Error de conexión detallado: {e}")
        st.stop()
