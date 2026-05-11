import os, requests, difflib, re
from database import get_db, fetchall_as_dicts

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.1-8b-instant"

# ── Normalizar texto: quitar tildes, pasar a minúsculas ──────
def normalizar(texto):
    texto = texto.lower().strip()
    reemplazos = {'á':'a','é':'e','í':'i','ó':'o','ú':'u','ü':'u','ñ':'n'}
    for k,v in reemplazos.items():
        texto = texto.replace(k,v)
    return texto

# ── Corrector ortográfico básico con difflib ─────────────────
def corregir_consulta(consulta, vocab):
    palabras = consulta.split()
    corregidas = []
    for palabra in palabras:
        if len(palabra) <= 3:
            corregidas.append(palabra)
            continue
        mejor = difflib.get_close_matches(normalizar(palabra), [normalizar(v) for v in vocab], n=1, cutoff=0.75)
        if mejor:
            # Devolver la palabra original del vocab que matchea
            for v in vocab:
                if normalizar(v) == mejor[0]:
                    corregidas.append(v)
                    break
            else:
                corregidas.append(palabra)
        else:
            corregidas.append(palabra)
    return ' '.join(corregidas)

# ── DB helpers ───────────────────────────────────────────────
def obtener_categorias():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT DISTINCT categoria FROM libros WHERE categoria IS NOT NULL AND categoria != '' ORDER BY categoria")
    cats = [row[0] for row in c.fetchall()]
    c.close(); conn.close()
    return cats

def obtener_vocab_libros():
    """Retorna lista de títulos + autores + categorías para corrección."""
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT titulo, autor, categoria FROM libros WHERE titulo IS NOT NULL")
    rows = c.fetchall()
    c.close(); conn.close()
    vocab = []
    for r in rows:
        for campo in r:
            if campo:
                vocab.extend(campo.split())
    return list(set(vocab))

def buscar_por_categoria_exacta(categoria):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM libros WHERE LOWER(categoria) = LOWER(%s) ORDER BY titulo", (categoria,))
    results = fetchall_as_dicts(c)
    c.close(); conn.close()
    return results

def buscar_libros_general(consulta):
    conn = get_db(); c = conn.cursor()
    q = f"%{consulta.lower().strip()}%"
    c.execute("""SELECT * FROM libros
        WHERE LOWER(titulo) LIKE %s OR LOWER(autor) LIKE %s OR LOWER(categoria) LIKE %s OR LOWER(editorial) LIKE %s
        ORDER BY categoria, titulo""", (q,q,q,q))
    results = fetchall_as_dicts(c)
    c.close(); conn.close()
    return results

# ── Formateo ─────────────────────────────────────────────────
def formatear_libro_simple(libro):
    disponible = "Sí" if libro.get("disponible", 0) >= 1 else "No"
    return (f"Título: {libro.get('titulo','N/A')}\n"
            f"Autor: {libro.get('autor','N/A') or 'N/A'}\n"
            f"Editorial: {libro.get('editorial','N/A') or 'N/A'}\n"
            f"Disponible: {disponible}\n"
            f"Categoría: {libro.get('categoria','N/A') or 'N/A'}")

def formatear_libros_por_categoria(libros):
    """Agrupa libros por categoría y los formatea."""
    grupos = {}
    for l in libros:
        cat = l.get('categoria','Sin categoría') or 'Sin categoría'
        grupos.setdefault(cat, []).append(l)
    partes = []
    for cat, items in sorted(grupos.items()):
        bloque = f"── {cat} ({len(items)} libro{'s' if len(items)!=1 else ''}) ──\n"
        bloque += "\n".join(
            f"• {l.get('titulo','?')} | Autor: {l.get('autor','?') or '?'} | {'Disponible' if l.get('disponible',0)>=1 else 'No disponible'}"
            for l in items
        )
        partes.append(bloque)
    return "\n\n".join(partes) if partes else "No se encontraron libros."

def formatear_lista_libros(libros):
    if not libros:
        return "No se encontraron libros."
    return "\n\n".join(f"{i}. {formatear_libro_simple(l)}" for i,l in enumerate(libros,1))

# ── Detectar categoría con fuzzy matching ────────────────────
def detectar_categoria_en_consulta(consulta):
    consulta_norm = normalizar(consulta)
    categorias = obtener_categorias()
    # Match exacto o contenido
    for cat in categorias:
        cat_norm = normalizar(cat)
        if cat_norm in consulta_norm or consulta_norm in cat_norm:
            return cat
    # Match fuzzy
    for cat in categorias:
        if difflib.SequenceMatcher(None, normalizar(cat), consulta_norm).ratio() > 0.55:
            return cat
    # Match por palabras
    palabras_consulta = consulta_norm.split()
    for cat in categorias:
        for palabra_cat in normalizar(cat).split():
            for palabra in palabras_consulta:
                if len(palabra) > 3 and len(palabra_cat) > 3:
                    if palabra in palabra_cat or palabra_cat in palabra:
                        return cat
    return None

# ── GROQ ─────────────────────────────────────────────────────
def llamar_groq(mensaje_usuario, contexto_libros=""):
    if not GROQ_API_KEY:
        return None
    sistema = """Sos ChacaBot, el asistente de la biblioteca del Colegio Chacabuco.
REGLAS:
- Respondé siempre en español, tono natural y amable.
- No uses emojis.
- Solo respondé sobre biblioteca, libros, préstamos, lectura o materias.
- Si te preguntan algo ajeno, decí: "Solo puedo ayudarte con temas de la biblioteca y sus libros."
- Presentate solo si te saludan.
- Si el usuario escribe con errores ortográficos, igual entendelo y respondé correctamente.
- Si el contexto tiene libros, presentalos agrupados por categoría de forma clara.
- Si el usuario pide "libros" sin especificar, preguntale qué tipo de libro o materia busca.
- Si detectás que busca algo específico (materia, autor, título), buscalo y mostralo.
FORMATO para lista de libros:
── [Categoría] ──
• [Título] | Autor: [Autor] | [Disponible/No disponible]"""

    payload = {
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user",   "content": f"CONTEXTO DE BIBLIOTECA:\n{contexto_libros}\n\nMENSAJE DEL USUARIO: {mensaje_usuario}"}
        ],
        "model": GROQ_MODEL,
        "temperature": 0.4,
        "max_tokens": 600
    }
    try:
        r = requests.post(GROQ_API_URL, json=payload,
                          headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                          timeout=15)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error Groq: {e}")
    return None

# ── Lógica principal ─────────────────────────────────────────
def procesar_consulta(consulta):
    consulta_orig  = consulta.strip()
    consulta_lower = normalizar(consulta_orig)

    # ── Saludos ──
    saludos = ["hola","buenas","hey","hi","buen dia","buenas tardes","buenas noches",
               "como estas","como andas","todo bien","que tal","como va","que onda",
               "hola chaca","chaca","que haces","como te va","buen dia"]
    if any(s in consulta_lower for s in saludos):
        respuesta = llamar_groq(consulta_orig, "El usuario está saludando.")
        return respuesta or "Hola, soy ChacaBot. ¿En qué libro te puedo ayudar hoy?"

    # ── Consulta genérica de libros sin especificar ──
    palabras_genericas = ["libros","libro","que tenes","que libros","catalogo","que hay","mostrame","mostrame libros"]
    es_consulta_generica = any(g == consulta_lower or consulta_lower == g for g in palabras_genericas)
    if es_consulta_generica or (len(consulta_lower.split()) <= 2 and any(g in consulta_lower for g in ["libro","libros","catalogo"])):
        cats = obtener_categorias()
        if cats:
            contexto = "Categorías disponibles en la biblioteca:\n" + "\n".join(f"- {c}" for c in cats)
            respuesta = llamar_groq(consulta_orig, contexto + "\nEl usuario pide libros de forma genérica, preguntale qué categoría o materia le interesa.")
            return respuesta or ("Tenemos libros en estas categorías:\n" + "\n".join(f"• {c}" for c in cats) + "\n\n¿Cuál te interesa?")
        return "No hay libros cargados en el catálogo por el momento."

    # ── Listar categorías ──
    if any(k in consulta_lower for k in ["categorias","materias","que categorias","que materias","temas disponibles"]):
        cats = obtener_categorias()
        if cats:
            contexto = "Categorías disponibles:\n" + "\n".join(f"- {c}" for c in cats)
            respuesta = llamar_groq(consulta_orig, contexto)
            return respuesta or ("Las categorías disponibles son:\n" + "\n".join(f"• {c}" for c in cats))
        return "No hay categorías cargadas en este momento."

    # ── Corregir ortografía con vocab de la BD ──
    try:
        vocab = obtener_vocab_libros()
        consulta_corregida = corregir_consulta(consulta_orig, vocab)
    except Exception:
        consulta_corregida = consulta_orig

    # ── Buscar por categoría ──
    categoria = detectar_categoria_en_consulta(consulta_corregida) or detectar_categoria_en_consulta(consulta_orig)
    if categoria:
        libros = buscar_por_categoria_exacta(categoria)
        if libros:
            contexto = f"Libros de la categoría '{categoria}':\n\n" + formatear_libros_por_categoria(libros)
            respuesta = llamar_groq(consulta_orig, contexto)
            return respuesta or f"Libros de {categoria}:\n\n{formatear_libros_por_categoria(libros)}"
        return f"No hay libros de la categoría '{categoria}' por el momento."

    # ── Búsqueda general ──
    libros = buscar_libros_general(consulta_corregida)
    if not libros and consulta_corregida != consulta_orig:
        libros = buscar_libros_general(consulta_orig)

    if libros:
        contexto = formatear_libros_por_categoria(libros)
        respuesta = llamar_groq(consulta_orig, f"Libros encontrados:\n\n{contexto}")
        return respuesta or f"Libros encontrados:\n\n{contexto}"

    # ── Sin resultados: preguntar mejor ──
    respuesta = llamar_groq(consulta_orig, "No se encontraron libros para esta búsqueda. Pedile al usuario más detalles o que pruebe con otra palabra.")
    return respuesta or "No encontré libros con esa búsqueda. ¿Podés darme más detalles o intentar con otro término?"