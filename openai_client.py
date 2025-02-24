import openai
import json
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

class Budget(BaseModel):
    pdf_title: str
    content: str

def generate_markdown(historial):
    try:
        prompt = [
            {"role": "system", "content": (
                "Sos un asistente que genera presupuestos y devuelve un JSON estructurado. El formato del JSON debe ser:\n"
                "{\n  \"pdf_title\": \"[título del PDF]\",\n  \"content\": \"[contenido en Markdown]\"\n}\n\n"
                "El título del PDF (`pdf_title`) debe ser la dirección mencionada en el mensaje del usuario (si existe), "
                "de lo contrario debe ser el nombre del/los propietario/s. En ultima instancia, debe ser \"Presupuesto\". El contenido (`content`) debe estar en Markdown con este formato de EJEMPLO:\n\n"
                "**Fecha:** [fecha]\n\n**Propietaria:** [nombre]\n\n**Dirección:** [dirección]\n\n"
                "**Contacto:** [contacto]\n\n---\n\n### **Presupuesto por Mano de Obra**\n\n"
                "### **Trabajos a Realizar:**\n\n1. [trabajo 1]\n2. [trabajo 2]\n...\n\n---\n\n"
                "### **Costo Total del Proyecto:** $[monto]\n\n---\n\n### **Materiales Aproximados:**\n\n- [material 1]\n- [material 2]\n...\n\n"
                "Todo campo faltante, ya sea propietario, contacto, dirección, trabajos a realizar, materiales aproximados, etc... deben ser OMITIDOS."
                "Si falta el contacto, no envies: Contacto: [Contacto]. Simplemente no envies el campo."
                "Si hay información extra, debe ser agregada de manera ordenada y estructurada, de la manera mas conveniente para el usuario."
                "No debes de seguir TODO al pie de la letra ya que habran distintas formas de presentar la información."
                "Tenes libertad para agregar/quitar/modificar y reestructurar el contenido segun sientas que es necesario, lo importante es mantener el formato y la estructura."
                "Tomá el mensaje del usuario y estructuralo en este formato JSON. Si es una modificación, ajustá el presupuesto anterior según las instrucciones."
            )}
        ] + historial

        # Nueva sintaxis con response_format para forzar JSON
        response = openai.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=prompt,
            max_tokens=5000,
            response_format=Budget  # Forzamos JSON estructurado
        )
        json_response = json.loads(response.choices[0].message.content.strip())
        return json_response
    except Exception as e:
        raise Exception(f"Error al generar Markdown con OpenAI: {str(e)}")