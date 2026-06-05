import tensorflow as tf
from openai import OpenAI
import streamlit as st

@st.cache_resource
def get_openai_client():
    # 1. Primero revisamos si la clave está guardada en los Secrets de la nube
    if "OPENAI_API_KEY" in st.secrets:
        return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    # 2. Si no está en los Secrets (significa que estás en tu PC local), usamos tu código de siempre
    try:
        with open("ApiKey.txt", "r") as f:
            key = f.read().strip()
        return OpenAI(api_key=key)
    except FileNotFoundError:
        st.error("📂 Error: No se encontró la API Key en los Secrets de Streamlit ni en 'ApiKey.txt'.")
        st.stop()

@st.cache_resource
def load_my_model():
    # Corregido de load_mostdel a load_model
    return tf.keras.models.load_model('modelo_PRO_perritos.h5')

def get_ia_response(client, system_instruction, full_context):
    resp = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[
            {"role": "system", "content": system_instruction}, 
            {"role": "user", "content": full_context}
        ], 
        temperature=0.3
    )
    return resp.choices[0].message.content