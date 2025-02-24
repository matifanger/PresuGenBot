# Estilo CSS para el PDF
CSS_ESTILO = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    @page {
        margin: 1cm;  /* Reducimos los márgenes de la página */
    }
    body {
        font-family: 'Inter', sans-serif;
        font-size: 12pt;
        line-height: 1.4;  /* Reducimos un poco el interlineado */
        color: black;
        margin: 0;  /* Eliminamos márgenes del body */
        padding: 0.5cm;  /* Padding interno más ajustado */
    }
    h1 {
        font-size: 18pt;
        font-weight: bold;
        color: black;
        text-align: center;
        margin-bottom: 15px;  /* Reducimos el margen inferior */
    }
    h3 {
        font-size: 16pt;
        font-weight: bold;
        color: black;
        margin-top: 15px;  /* Reducimos el margen superior */
        margin-bottom: 10px;
    }
    p, li {
        margin: 3px 0;  /* Reducimos los márgenes entre párrafos y lista */
        color: black;
    }
    hr {
        border: 0;
        border-top: 1px solid #ccc;
        opacity: 0.5;
        margin: 10px 0;  /* Reducimos el espacio alrededor del separador */
    }
</style>
"""