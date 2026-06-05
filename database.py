import pg8000
import streamlit as st

def get_db_connection():
    try:
        if "DB_HOST" in st.secrets:
            # Creamos la conexión a AWS
            conn = pg8000.connect(
                host=st.secrets["DB_HOST"],
                database=st.secrets["DB_NAME"],
                user=st.secrets["DB_USER"],
                password=st.secrets["DB_PASSWORD"],
                port=int(st.secrets["DB_PORT"]),
                timeout=5
            )
        else:
            # Creamos la conexión Local
            conn = pg8000.connect(
                host="localhost",
                database="petskin_db",
                user="postgres",
                password="Farjevasquez16*",
                port=5432,
                timeout=3
            )
        
        # 🔥 TRUCO CLAVE: Configuramos la conexión para que use diccionarios de forma nativa
        conn.run_mapper = pg8000.types.dict_row_mapper
        return conn

    except Exception as e:
        st.error(f"❌ Error de conexión detallado: {e}")
        st.stop()
