import pg8000
import streamlit as st

# Creamos una clase limpia para que actúe como convertidor automático a diccionario
class DictCursor:
    def __init__(self, connection):
        self.cursor = connection.cursor()
    
    def execute(self, query, params=None):
        self.cursor.execute(query, params) if params else self.cursor.execute(query)
        return self
        
    def fetchone(self):
        row = self.cursor.fetchone()
        if not row: return None
        # Mapeamos los nombres de las columnas con sus valores
        columns = [col['name'] for col in self.cursor.description]
        return dict(zip(columns, row))
        
    def fetchall(self):
        rows = self.cursor.fetchall()
        if not rows: return []
        columns = [col['name'] for col in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]
        
    def close(self):
        self.cursor.close()

# Envoltura para la conexión estándar que use nuestro DictCursor
class DictConnection:
    def __init__(self, conn):
        self.conn = conn
    def cursor(self, *args, **kwargs):
        return DictCursor(self.conn)
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()

def get_db_connection():
    try:
        if "DB_HOST" in st.secrets:
            raw_conn = pg8000.connect(
                host=st.secrets["DB_HOST"],
                database=st.secrets["DB_NAME"],
                user=st.secrets["DB_USER"],
                password=st.secrets["DB_PASSWORD"],
                port=int(st.secrets["DB_PORT"]),
                timeout=5
            )
        else:
            raw_conn = pg8000.connect(
                host="localhost",
                database="petskin_db",
                user="postgres",
                password="Farjevasquez16*",
                port=5432,
                timeout=3
            )
        # Devolvemos la conexión protegida que ya entrega diccionarios nativos
        return DictConnection(raw_conn)
    except Exception as e:
        st.error(f"❌ Error de conexión detallado: {e}")
        st.stop()
