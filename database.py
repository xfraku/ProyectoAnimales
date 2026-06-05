import pg8000
import streamlit as st

class DictCursor:
    def __init__(self, connection):
        self.cursor = connection.cursor()
    
    def execute(self, query, params=None):
        self.cursor.execute(query, params) if params else self.cursor.execute(query)
        return self
        
    def fetchone(self):
        row = self.cursor.fetchone()
        if not row: return None
        # 🔥 CORRECCIÓN: pg8000 maneja las columnas por índice. El nombre es el elemento [0]
        columns = [col[0] for col in self.cursor.description]
        return dict(zip(columns, row))
        
    def fetchall(self):
        rows = self.cursor.fetchall()
        if not rows: return []
        # 🔥 CORRECCIÓN: Mismo ajuste para el fetchall
        columns = [col[0] for col in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]
        
    def close(self):
        self.cursor.close()

# Esto lo dejas exactamente igual como estaba
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
        return DictConnection(raw_conn)
    except Exception as e:
        st.error(f"❌ Error de conexión detallado: {e}")
        st.stop()
