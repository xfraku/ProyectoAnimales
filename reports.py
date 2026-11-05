"""Paginated Unicode PDF generated from persisted consultation data."""
import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fpdf import FPDF

from domain import DISCLAIMER, THRESHOLD, diagnosis
from settings import ROOT


class Report(FPDF):
    def header(self):
        self.set_font('Noto', 'B', 13)
        self.set_text_color(15, 98, 91)
        self.cell(0, 8, 'PetSkin AI  /  Reporte de consulta', new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(184, 215, 210)
        self.line(self.l_margin, self.y + 1, self.w - self.r_margin, self.y + 1)
        self.ln(6)

    def footer(self):
        self.set_y(-22)
        self.set_font('Noto', '', 8)
        self.set_text_color(80, 88, 92)
        self.multi_cell(0, 4, DISCLAIMER, new_x='LMARGIN', new_y='NEXT')
        self.cell(0, 5, f'Página {self.page_no()}/{{nb}}', align='R')


def clean_text(value):
    # Preserve all supported Unicode, replace only unsupported pictographs/control characters.
    value = str(value or '')
    value = re.sub(r'[*`#]', '', value)
    return ''.join(c if c in '\n\t' or 32 <= ord(c) <= 0xFFFF else ' ' for c in value)


def generate_report(case, messages, image_bytes=None):
    pdf = Report()
    pdf.add_font('Noto', '', str(ROOT / 'assets/fonts/NotoSans-Regular.ttf'))
    pdf.add_font('Noto', 'B', str(ROOT / 'assets/fonts/NotoSans-Bold.ttf'))
    pdf.set_margins(16, 12, 16)
    pdf.set_auto_page_break(True, 28)
    pdf.alias_nb_pages()
    pdf.set_title(f"PetSkin AI - Consulta {case['id']}")
    pdf.set_author('PetSkin AI')
    pdf.add_page()

    def paragraph(text, bold=False, size=10):
        pdf.set_text_color(35, 47, 53)
        pdf.set_font('Noto', 'B' if bold else '', size)
        pdf.multi_cell(0, 5.5, clean_text(text), new_x='LMARGIN', new_y='NEXT', align='L')
        pdf.ln(2)

    def heading(text):
        if pdf.will_page_break(18):
            pdf.add_page()
        pdf.set_fill_color(232, 244, 241)
        pdf.set_font('Noto', 'B', 11)
        pdf.cell(0, 9, text, fill=True, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(3)

    when = case['fecha'].strftime('%d/%m/%Y %H:%M:%S')
    paragraph(f"Consulta #{case['id']} · {when} (hora de Lima)", bold=True)
    paragraph('Documento de orientación preliminar · Emitido: ' +
              datetime.now(ZoneInfo('America/Lima')).strftime('%d/%m/%Y %H:%M'))
    pet = case.get('patient_snapshot') or {}
    heading('Ficha del paciente')
    if pet:
        paragraph(f"Nombre: {pet.get('nombre', '')}\nRaza: {pet.get('raza', '')} · Color: {pet.get('color') or 'No registrado'}\n"
                  f"Peso: {pet.get('peso', '')} kg · Tamaño: {pet.get('tamano', '')}")
        paragraph('Antecedentes: ' + (pet.get('historial') or 'Sin antecedentes registrados.'))
        paragraph(pet.get('origen', 'Datos registrados al crear la consulta'), size=8)
    else:
        paragraph('Esta consulta antigua no tiene un paciente vinculado.')
    if image_bytes:
        heading('Fotografía analizada')
        pdf.image(io.BytesIO(image_bytes), w=90, h=65, keep_aspect_ratio=True)
        pdf.ln(4)
    else:
        paragraph('Fotografía no incluida: no estaba disponible al generar este documento.', size=8)
    heading('Resultado del análisis')
    paragraph(diagnosis(case['diagnostico_ml'], case['confianza_ml']), bold=True, size=13)
    paragraph(f"Confianza del modelo: {case['confianza_ml']:.2f} %. Umbral: {THRESHOLD:.0f} %. "
              'Este puntaje no representa exactitud clínica ni confirma una enfermedad.')
    if case['confianza_ml'] < THRESHOLD:
        paragraph('La confianza es insuficiente. No se asigna un diagnóstico específico a la imagen.')
    if case.get('urgent'):
        heading('Alerta de atención veterinaria')
        paragraph(case.get('alert_reason') or 'Solicita una evaluación veterinaria pronta.')
        paragraph('Si el animal presenta una emergencia, acude a un servicio veterinario; no esperes una videollamada.')
    heading('Cuidados preventivos')
    paragraph(case.get('advice') or 'Consulta al veterinario para recibir orientación adecuada.')
    heading('Resumen y orientación')
    last_id = messages[-1]['id'] if messages else 0
    if case.get('summary') and case.get('summary_message_id') == last_id:
        paragraph(case['summary'])
    elif not messages:
        paragraph('Aún no se ha realizado una conversación de orientación. No se ha indicado tratamiento.')
    else:
        paragraph('No hay un resumen actualizado. La siguiente transcripción contiene todas las indicaciones '
                  'y aclaraciones registradas, en orden cronológico.')
    if messages:
        heading('Conversación completa')
        paragraph('Las respuestas son orientativas. Las aclaraciones posteriores pueden corregir indicaciones anteriores.', size=9)
        for msg in messages:
            paragraph('Usuario' if msg['role'] == 'user' else 'Asistente de IA', bold=True)
            paragraph(msg['content'])
    paragraph(DISCLAIMER, bold=True, size=9)
    return bytes(pdf.output())
