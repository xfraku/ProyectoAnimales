import re
import os
from fpdf import FPDF

def es_correo_valido(correo):
    patron = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(patron, correo) is not None

def generar_hoja_tratamiento(datos_mascota, diagnostico, tratamiento_ia, img_path):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado con Estilo
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(40, 40, 120) 
    pdf.cell(190, 20, "HOJA DE TRATAMIENTO - PETSKIN AI", ln=True, align="C")
    
    pdf.set_draw_color(40, 40, 120)
    pdf.line(10, 30, 200, 30)
    
    if img_path and os.path.exists(img_path):
        pdf.image(img_path, x=70, y=35, w=70)
        pdf.ln(85)
    
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 10, "  INFORMACION DE LA MASCOTA", ln=True, fill=True)
    
    pdf.set_font("Helvetica", "", 12)
    pdf.ln(2)
    pdf.cell(95, 10, f"Nombre: {datos_mascota.get('nombre', 'N/A')}")
    pdf.cell(95, 10, f"Raza: {datos_mascota.get('raza', 'N/A')}", ln=True)
    pdf.cell(95, 10, f"Peso: {datos_mascota.get('peso', 'N/A')} kg")
    pdf.cell(95, 10, f"Tamano: {datos_mascota.get('tamano', 'N/A')}", ln=True)
    
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, "Historial Clinico Previo:", ln=True)
    pdf.set_font("Helvetica", "", 11)
    hist = datos_mascota.get('historial', 'No aplica')
    pdf.multi_cell(190, 7, hist if hist else "No aplica")
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(220, 230, 250)
    pdf.cell(190, 10, f"  DIAGNOSTICO DETECTADO: {diagnostico}", ln=True, fill=True)
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, "Tratamiento Sugerido e Indicaciones:", ln=True)
    pdf.set_font("Helvetica", "", 11)
    
    texto_limpio = tratamiento_ia.replace("**", "")
    texto_final = texto_limpio.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(190, 7, texto_final)
    
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(190, 5, "AVISO: Este reporte es una sugerencia basada en IA. No reemplaza el juicio de un veterinario colegiado.", align="C")
    
    return pdf.output(dest='S').encode('latin1') if isinstance(pdf.output(), str) else pdf.output()
