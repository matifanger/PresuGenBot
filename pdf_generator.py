from markdown import markdown
import weasyprint
from config import CSS_ESTILO

def generate_pdf(json_data, output_file="presupuesto.pdf"):
    try:
        # Extraemos pdf_title y content del JSON
        pdf_title = json_data["pdf_title"]
        content = json_data["content"]
        
        # Construimos el HTML con el título dinámico
        html = CSS_ESTILO + markdown(markdown_text)
        weasyprint.HTML(string=html).write_pdf(output_file)
        return output_file
    except Exception as e:
        raise Exception(f"Error al generar el PDF: {str(e)}")


from markdown import markdown
import weasyprint
from config import CSS_ESTILO

def generate_pdf(json_data, output_file="presupuesto.pdf"):
    try:
        # Extraemos pdf_title y content del JSON
        pdf_title = json_data["pdf_title"]
        content = json_data["content"]

        # Si no existe pdf_title, lo seteamos como "Presupuesto"
        if not pdf_title:
            pdf_title = "Presupuesto"
        
        # Construimos el HTML con el título dinámico
        html = CSS_ESTILO + "Presupuesto" + markdown(content)  # Cambié markdown_text por content
        weasyprint.HTML(string=html).write_pdf(pdf_title+'.pdf')
        return pdf_title+'.pdf'
    except Exception as e:
        raise Exception(f"Error al generar el PDF: {str(e)}")