import os
import requests
import difflib
from database import get_db, fetchall_as_dicts

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

def obtener_categorias():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT categoria FROM libros WHERE categoria IS NOT NULL AND categoria != '' ORDER BY categoria")
    cats = [row[0] for row in c.fetchall()]
    c.close()
    conn.close()
    return cats

def buscar_por_categoria_exacta(categoria_buscada):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM libros WHERE LOWER(categoria) = LOWER(%s) ORDER BY titulo", (categoria_buscada,))
    results = fetchall_as_dicts(c)
    c.close()
    conn.close()
    return results

def buscar_libros_general(consulta):
    conn = get_db()
    c = conn.cursor()
    q = f"%{consulta.lower().strip()}%"
    c.execute("""SELECT * FROM libros
        WHERE LOWER(titulo) LIKE %s OR LOWER(autor) LIKE %s OR LOWER(categoria) LIKE %s OR LOWER(editorial) LIKE %s
        ORDER BY categoria, titulo""", (q, q, q, q))
    resultados = fetchall_as_dicts(c)
    c.close()
    conn.close()
    return resultados

def formatear_libro_simple(libro):
    disponible = "Sí" if libro.get("disponible", 0) >= 1 else "No"
    return f"""Nombre: {libro.get('titulo', 'N/A')}
Capítulos: {libro.get('capitulo', 'N/A') or 'N/A'}
Editorial: {libro.get('editorial', 'N/A') or 'N/A'}
Autor: {libro.get('autor', 'N/A') or 'N/A'}
Disponible: {disponible}
Categoría: {libro.get('categoria', 'N/A') or 'N/A'}"""

def formatear_lista_libros(libros):
    if not libros:
        return "No se encontraron libros."
    return "\n\n".join(f"{i}. {formatear_libro_simple(l)}" for i, l in enumerate(libros, 1))

def detectar_categoria_en_consulta(consulta):
    consulta_lower = consulta.lower().strip()
    categorias = obtener_categorias()
    for cat in categorias:
        cat_lower = cat.lower()
        if cat_lower in consulta_lower or consulta_lower in cat_lower:
            return cat
        if difflib.SequenceMatcher(None, cat_lower, consulta_lower).ratio() > 0.6:
            return cat
    palabras_consulta = consulta_lower.split()
    for cat in categorias:
        for palabra_cat in cat.lower().split():
            for palabra in palabras_consulta:
                if len(palabra) > 3 and len(palabra_cat) > 3 and (palabra in palabra_cat or palabra_cat in palabra):
                    return cat
    return None

def llamar_groq(mensaje_usuario, contexto_libros=""):
    if not GROQ_API_KEY:
        return None
    sistema = """Eres ChacaBot, una bibliotecaria amable y conversacional del Colegio Chacabuco.
REGLAS IMPORTANTES:
Respondé siempre en español, con tono natural y amable.
Sé clara y profesional, pero no robótica.
No uses emojis.
Solo presentate como ChacaBot cuando te saluden.
RESTRICCIÓN ESTRICTA: SOLO responde sobre temas relacionados con la biblioteca, libros, préstamos o lectura.
Si pregunta sobre temas ajenos, respondé: "Soy ChacaBot y solo puedo ayudarte con información sobre la biblioteca y sus libros."
FORMATO para mostrar libros:
Nombre: [título]
Capítulos: [capítulo]
Editorial: [editorial]
Autor: [autor]
Disponible: [Sí/No]
Categoría: [categoría]"""
    payload = {
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": f"CONTEXTO: {contexto_libros}\n\nUSUARIO: {mensaje_usuario}"}
        ],
        "model": GROQ_MODEL,
        "temperature": 0.5,
        "max_tokens": 500
    }
    try:
        response = requests.post(GROQ_API_URL, json=payload,
                                 headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                                 timeout=15)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"❌ Error Groq: {e}")
    return None

def procesar_consulta(consulta):
    consulta_lower = consulta.lower().strip()
    saludos = ["hola", "buenas", "hey", "hi", "buen dia", "buenas tardes", "buenas noches",
               "como estas", "como andas", "todo bien", "que tal", "como va", "que onda",
               "hola chaca", "chaca", "qué hacés", "que haces", "como te va"]
    if any(s in consulta_lower for s in saludos):
        respuesta = llamar_groq(consulta, "El usuario está saludando. Respondé amablemente y preguntá en qué podés ayudar.")
        return respuesta or "¡Hola! Soy ChacaBot. ¿En qué libro te puedo ayudar hoy?"

    if any(k in consulta_lower for k in ["que libros", "q libros", "que tenes", "categorias", "materias", "catalogo", "que hay"]):
        cats = obtener_categorias()
        if cats:
            contexto = "Categorías disponibles:\n" + "\n".join(f"- {cat}" for cat in cats)
            respuesta = llamar_groq(consulta, contexto)
            return respuesta or "Tenemos estas categorías:\n" + "\n".join(f"• {cat}" for cat in cats)
        return "No hay categorías cargadas en este momento."

    categoria_detectada = detectar_categoria_en_consulta(consulta)
    if categoria_detectada:
        libros = buscar_por_categoria_exacta(categoria_detectada)
        if libros:
            contexto = formatear_lista_libros(libros)
            respuesta = llamar_groq(consulta, contexto)
            return respuesta or f"Libros de {categoria_detectada}:\n\n{contexto}"
        return f"No hay libros cargados de la categoría '{categoria_detectada}'."

    if len(consulta_lower.split()) >= 2:
        libros = buscar_libros_general(consulta)
        if libros:
            contexto = formatear_lista_libros(libros)
            respuesta = llamar_groq(consulta, contexto)
            return respuesta or f"Libros encontrados:\n\n{contexto}"
        return "No encontré libros con esa búsqueda. Probá con otro término."

    respuesta = llamar_groq(consulta, "Consulta corta. Preguntá en qué podés ayudar con los libros.")
    return respuesta or "¿En qué te ayudo? Podés preguntarme por categorías o buscar un título."