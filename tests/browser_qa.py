"""Executable QA of the local Streamlit harness at 127.0.0.1:8517."""
import io
import json
import re
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright, expect

OUT=Path('test-output/ui')
OUT.mkdir(parents=True,exist_ok=True)


def snapshot(page,name):
    # Streamlit replaces the page progressively; wait for stale widgets to disappear.
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
    assert page.locator('[data-testid="stException"]').count()==0
    assert page.get_by_text('No se pudo completar esta acción.',exact=False).count()==0
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')


def run():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        page.goto('http://127.0.0.1:8517')
        expect(page.get_by_role('heading',name='Bienvenido a PetSkin')).to_be_visible(timeout=30000)
        snapshot(page,'01_login_desktop')
        page.get_by_label('Usuario',exact=True).fill('usuarioqa')
        page.get_by_label('Contraseña',exact=True).fill('12345')
        page.get_by_role('button',name='Iniciar sesión',exact=True).click()
        expect(page.get_by_role('heading',name='Nueva consulta',exact=True)).to_be_visible()
        page.get_by_text('Mis mascotas',exact=True).click()
        expect(page.get_by_role('heading',name='Mis mascotas')).to_be_visible()
        snapshot(page,'02_mascotas')
        page.get_by_text('Nueva consulta',exact=True).first.click()
        with page.expect_file_chooser() as chooser:
            page.get_by_role('button',name=re.compile('Upload')).last.click()
        output=io.BytesIO();Image.new('RGB',(320,240),(150,110,90)).save(output,'JPEG')
        chooser.value.set_files({'name':'fixture_canina.jpg','mimeType':'image/jpeg','buffer':output.getvalue()})
        expect(page.get_by_role('button',name='Analizar fotografía')).to_be_enabled()
        page.get_by_role('button',name='Analizar fotografía').click()
        expect(page.get_by_role('heading',name='Resultado preliminar')).to_be_visible(timeout=30000)
        snapshot(page,'03_resultado_desktop')
        with page.expect_download() as download:
            page.get_by_role('button',name='Descargar reporte PDF').click()
        download.value.save_as(str(OUT/'reporte_navegador.pdf'))
        assert (OUT/'reporte_navegador.pdf').read_bytes().startswith(b'%PDF')
        page.get_by_role('button',name='Ver reporte PDF',exact=True).click()
        expect(page.get_by_text('Vista previa del reporte PDF',exact=True)).to_be_visible()
        # The built-in viewer must render an embedded canvas, not an empty iframe.
        page.wait_for_timeout(1800)
        snapshot(page,'04_pdf_preview')
        link=page.get_by_role('link',name='Llamar veterinario por WhatsApp')
        assert link.get_attribute('href') == 'https://wa.me/12025550123'
        page.get_by_label('Tu consulta',exact=True).fill('Se rasca desde ayer. ¿Qué cuidados puedo darle?')
        page.get_by_role('button',name='Enviar consulta',exact=True).click()
        expect(page.get_by_text('Respuesta guardada en la consulta.',exact=True)).to_be_visible()
        expect(page.get_by_text('Mantén la zona limpia',exact=False)).to_be_visible()
        page.get_by_role('button',name='Actualizar resumen del reporte').click()
        expect(page.get_by_text('Resumen actualizado y disponible en el PDF.',exact=True)).to_be_visible()
        page.set_viewport_size({'width':390,'height':844})
        snapshot(page,'05_resultado_mobile')
        page.set_viewport_size({'width':1440,'height':1000})
        page.get_by_role('button',name='Eliminar esta consulta',exact=True).click()
        expect(page.get_by_role('dialog')).to_be_visible()
        snapshot(page,'06_confirmacion')
        page.get_by_role('button',name='Cancelar',exact=True).click()
        expect(page.get_by_role('dialog')).to_have_count(0)
        page.get_by_text('Historial',exact=True).click()
        expect(page.get_by_role('heading',name='Historial de consultas')).to_be_visible()
        snapshot(page,'07_historial')
        page.get_by_role('button',name='Cerrar sesión',exact=True).click()
        page.get_by_label('Usuario',exact=True).fill('adminqa')
        page.get_by_label('Contraseña',exact=True).fill('12345')
        page.get_by_role('button',name='Iniciar sesión',exact=True).click()
        page.get_by_text('Usuarios',exact=True).click()
        expect(page.get_by_role('heading',name='Gestión de usuarios')).to_be_visible()
        snapshot(page,'08_usuarios')
        page.get_by_text('Métricas y auditoría',exact=True).first.click()
        page.get_by_role('button',name='Ver gráfico',exact=True).click()
        snapshot(page,'09_metricas')
        page.get_by_role('tab',name='Auditoría',exact=True).click()
        snapshot(page,'10_auditoria')
        page.get_by_role('tab',name='Consejos preventivos',exact=True).click()
        snapshot(page,'11_consejos')
        page.get_by_role('tab',name='Accesos y archivos',exact=True).click()
        snapshot(page,'12_accesos')
        browser.close()
    print(json.dumps({'browser':'Chromium','desktop':'1440x1000','mobile':'390x844','status':'passed','screenshots':12}))


if __name__=='__main__':
    run()
