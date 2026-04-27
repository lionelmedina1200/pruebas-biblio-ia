import os
import requests
import difflib
from database import get_db

# Configuración de GROQ
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

def obtener_categorias():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT categoria FROM libros WHERE categoria IS NOT NULL AND categoria != '' ORDER BY categoria")
    cats = [row[0] for row in c.fetchall()]
    conn.close()
    return cats

def buscar_por_categoria_exacta(categoria_buscada):
    conn = get_db()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    cur = conn.cursor()
    cur.execute("SELECT * FROM libros WHERE LOWER(categoria) = LOWER(?) ORDER BY titulo", (categoria_buscada,))
    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results

def buscar_libros_general(consulta):
    conn = get_db()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    cur = conn.cursor()
    q = consulta.lower().strip()
    cur.execute("""
        SELECT * FROM libros 
        WHERE LOWER(titulo) LIKE ? OR LOWER(autor) LIKE ? OR LOWER(categoria) LIKE ? OR LOWER(editorial) LIKE ?
        ORDER BY categoria, titulo
    """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
    resultados = [dict(row) for row in cur.fetchall()]
    conn.close()
    return resultados

def formatear_libro_simple(libro):
    disponible = "Sí" if libro.get("disponible", 0) == 1 else "No"
    return f"""Nombre: {libro.get('titulo', 'N/A')}
Capítulos: {libro.get('capitulo', 'N/A') or 'N/A'}
Editorial: {libro.get('editorial', 'N/A') or 'N/A'}
Autor: {libro.get('autor', 'N/A') or 'N/A'}
Disponible: {disponible}
Categoría: {libro.get('categoria', 'N/A') or 'N/A'}"""

def formatear_lista_libros(libros):
    if not libros:
        return "No se encontraron libros."
    resultado = ""
    for i, libro in enumerate(libros, 1):
        if i > 1:
            resultado += "\n\n"
        resultado += f"{i}. "
        resultado += formatear_libro_simple(libro)
    return resultado

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
        cat_lower = cat.lower()
        palabras_cat = cat_lower.split()
        for palabra in palabras_consulta:
            if len(palabra) > 3:
                for palabra_cat in palabras_cat:
                    if len(palabra_cat) > 3 and (palabra in palabra_cat or palabra_cat in palabra):
                        return cat
    return None

def llamar_groq(mensaje_usuario, contexto_libros=""):
    if not GROQ_API_KEY:
        print("⚠️ No hay GROQ_API_KEY configurada")
        return None
    
    sistema = """Eres ChacaBot, una bibliotecaria amable y conversacional del Colegio Chacabuco.

REGLAS IMPORTANTES:
1. Respondé siempre en español, con tono natural y amable.
2. Sé clara y profesional, pero no robótica.
3. No uses emojis.
4. Solo presentate como ChacaBot cuando te saluden.
5. RESTRICCIÓN ESTRICTA: SOLO responde sobre temas relacionados con la biblioteca, libros, préstamos o lectura.
6. Si el usuario saluda o pregunta cómo estás, respondé naturalmente y luego preguntá en qué podés ayudar con los libros.
7. Si pregunta sobre temas ajenos (recetas, clima, juegos, etc.), respondé amablemente: "Soy ChacaBot y solo puedo ayudarte con información sobre la biblioteca y sus libros. ¿Hay algún libro que estés buscando?"

FORMATO para mostrar libros (SOLO cuando muestres resultados):
Nombre: [título]
Capítulos: [capítulo]
Editorial: [editorial]
Autor: [autor]
Disponible: [Sí/No]
Categoría: [categoría]
"""
    
    mensajes = [
        {"role": "system", "content": sistema},
        {"role": "user", "content": f"CONTEXTO: {contexto_libros}\n\nUSUARIO: {mensaje_usuario}"}
    ]
    
    payload = {
        "messages": mensajes,
        "model": GROQ_MODEL,
        "temperature": 0.5,
        "max_tokens": 500
    }
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🚀 Llamando a Groq...")
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            respuesta = data['choices'][0]['message']['content'].strip()
            print("✅ Respuesta de Groq recibida")
            return respuesta
        else:
            print(f"❌ Error Groq {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None

def procesar_consulta(consulta):
    print(f"\n🔍 Consulta recibida: '{consulta}'")
    consulta_lower = consulta.lower().strip()
    
    # 1. SALUDOS Y CHARLA CASUAL (Lista ampliada)
    saludos = [
        "hola", "buenas", "hey", "hi", "buen dia", "buenas tardes", "buenas noches",
        "como estas", "como andas", "todo bien", "que tal", "como va", "que onda", 
        "hola chaca", "chaca", "qué hacés", "que haces", "como te va"
    ]
    if any(s in consulta_lower for s in saludos):
        print("→ Detectado: Saludo o charla casual")
        contexto = "El usuario está saludando o haciendo charla casual. Respondé de forma amable y breve, presentándote como ChacaBot y preguntando en qué puedes ayudar con la biblioteca."
        respuesta = llamar_groq(consulta, contexto)
        return respuesta if respuesta else "¡Hola! Soy ChacaBot, todo bien por acá. ¿En qué libro te puedo ayudar hoy?"
    
    # 2. CONSULTA SOBRE CATEGORÍAS O CATÁLOGO
    if any(k in consulta_lower for k in ["que libros", "q libros", "que tenes", "q tenes", "tipos de libros", "categorias", "materias", "catalogo", "que hay", "q hay", "lista de"]):
        print("→ Detectado: Consulta de catálogo/categorías")
        cats = obtener_categorias()
        if cats:
            contexto = "Categorías disponibles:\n\n" + "\n".join(f"- {cat}" for cat in cats)
            print(f"→ Categorías encontradas: {len(cats)}")
            respuesta = llamar_groq(consulta, contexto)
            return respuesta if respuesta else f"Tenemos estas categorías:\n\n" + "\n".join(f"• {cat}" for cat in cats)
        return "No hay categorías cargadas en este momento."
    
    # 3. BÚSQUEDA POR CATEGORÍA ESPECÍFICA
    categoria_detectada = detectar_categoria_en_consulta(consulta)
    if categoria_detectada:
        print(f"→ Detectada categoría: {categoria_detectada}")
        libros = buscar_por_categoria_exacta(categoria_detectada)
        
        if libros:
            print(f"→ Encontrados {len(libros)} libros")
            contexto = formatear_lista_libros(libros)
            respuesta = llamar_groq(consulta, contexto)
            return respuesta if respuesta else f"Estos son los libros de {categoria_detectada}:\n\n{contexto}"
        else:
            return f"No hay libros cargados de la categoría '{categoria_detectada}'."
    
    # 4. BÚSQUEDA GENERAL (Título, Autor, etc.)
    if len(consulta_lower.split()) >= 2:
        print("→ Búsqueda general")
        libros = buscar_libros_general(consulta)
        
        if libros:
            print(f"→ Encontrados {len(libros)} libros")
            contexto = formatear_lista_libros(libros)
            respuesta = llamar_groq(consulta, contexto)
            return respuesta if respuesta else f"Libros encontrados:\n\n{contexto}"
        else:
            return "No encontré libros con esa búsqueda. Probá con otro término o preguntame '¿Qué categorías hay?'"
    
    # 5. CONSULTAS CORTAS O NO ENTENDIDAS
    print("→ Consulta corta, intentando respuesta general")
    respuesta = llamar_groq(consulta, "El usuario hizo una consulta muy corta. Respondé amablemente preguntando en qué puedes ayudar con los libros.")
    return respuesta if respuesta else "Podés preguntarme por categorías como 'biología', buscar un título o autor, o decirme 'hola' para charlar. ¿En qué te ayudo?"