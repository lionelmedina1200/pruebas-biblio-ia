import os
import traceback
import requests as http_requests
from flask import Flask, render_template, request, jsonify, session, redirect
from database import init_db, get_db, verificar_usuario, registrar_usuario, fetchall_as_dicts, fetchone_as_dict
from google_auth_oauthlib.flow import Flow
from ai_engine import procesar_consulta
from auth import login_required, bibliotecario_required, admin_required


def registrar_log(conn_cursor, usuario_id, usuario_nombre, accion, tabla, registro_id, detalles):
    """Registra una accion en logs_actividad (silencioso si falla)."""
    try:
        conn_cursor.execute(
            """INSERT INTO logs_actividad (usuario_id, usuario_nombre, accion, tabla_afectada, registro_id, detalles)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (usuario_id, usuario_nombre, accion, tabla, registro_id, str(detalles))
        )
    except Exception:
        pass

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "biblioteca_secreta_segura_2026_cambiame")

# ── Google OAuth config ──────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# En Render (HTTPS) no hace falta; en local (HTTP) sí
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "0")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]

def make_google_flow():
    """Crea el flow de OAuth2 con las credenciales de entorno."""
    return Flow.from_client_config(
        {
            "web": {
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": ["https://pruebas-biblio-ia.onrender.com/auth/google/callback"],
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri="https://pruebas-biblio-ia.onrender.com/auth/google/callback",
    )

@app.route("/auth/google")
def auth_google():
    """Redirige al usuario a la pantalla de consentimiento de Google."""
    if not GOOGLE_CLIENT_ID:
        return "Error: Google OAuth no está configurado en el servidor.", 500
    flow = make_google_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account",   # fuerza elegir cuenta siempre
    )
    session["oauth_state"] = state
    return redirect(auth_url)

@app.route("/auth/google/callback")
def auth_google_callback():
    """Google redirige acá después de que el usuario aceptó."""
    # Verificar state para prevenir CSRF
    if request.args.get("state") != session.get("oauth_state"):
        return redirect("/?error=oauth_state")

    flow = make_google_flow()
    try:
        flow.fetch_token(authorization_response=request.url.replace("http://", "https://"))
    except Exception as e:
        traceback.print_exc()
        return redirect("/?error=oauth_token")

    # Obtener info del usuario desde Google
    creds = flow.credentials
    userinfo_resp = http_requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"}
    )
    if userinfo_resp.status_code != 200:
        return redirect("/?error=userinfo")

    ginfo = userinfo_resp.json()
    google_id = ginfo.get("id")
    email     = ginfo.get("email", "")
    nombre    = ginfo.get("name", email.split("@")[0])
    picture   = ginfo.get("picture", "")

    if not google_id or not email:
        return redirect("/?error=no_email")

    # Buscar o crear el alumno en la BD
    try:
        conn = get_db()
        c = conn.cursor()

        # Buscar por google_id o por email
        c.execute("SELECT id, username, nombre, email, rol FROM usuarios WHERE google_id = %s OR email = %s LIMIT 1",
                  (google_id, email))
        row = fetchone_as_dict(c)

        if row:
            # Si existe pero no tiene google_id aún, actualizarlo
            if not row.get("google_id"):
                c.execute("UPDATE usuarios SET google_id = %s WHERE id = %s", (google_id, row["id"]))
                conn.commit()
            # Solo alumnos pueden loguarse con Google
            if row["rol"] != "alumno":
                c.close(); conn.close()
                return redirect("/?error=no_alumno")
            usuario_db = row
        else:
            # Crear nuevo alumno
            username = email.split("@")[0]  # username = parte antes del @
            # Evitar username duplicado
            c.execute("SELECT COUNT(*) FROM usuarios WHERE username = %s", (username,))
            count = c.fetchone()
            count = count[0] if count else 0
            if count:
                username = f"{username}_{google_id[:6]}"
            c.execute("""
                INSERT INTO usuarios (username, password, nombre, email, rol, google_id)
                VALUES (%s, %s, %s, %s, 'alumno', %s)
                RETURNING id, username, nombre, email, rol
            """, (username, "__google__", nombre, email, google_id))
            usuario_db = fetchone_as_dict(c)
            conn.commit()

        c.close(); conn.close()

        session["usuario"] = {
            "id":       usuario_db["id"],
            "username": usuario_db["username"],
            "nombre":   usuario_db["nombre"],
            "email":    usuario_db["email"],
            "rol":      usuario_db["rol"],
            "picture":  picture,
        }
        return redirect("/")

    except Exception as e:
        traceback.print_exc()
        return redirect("/?error=db")

# Inicializar DB una sola vez al arrancar (no en cada request)
_db_initialized = False

@app.before_request
def setup_db():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    try:
        data = request.json or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        if not username or not password:
            return jsonify({"error": "Usuario y contraseña son obligatorios"}), 400
        usuario = verificar_usuario(username, password)
        if usuario:
            session["usuario"] = {
                "id": usuario["id"],
                "username": usuario["username"],
                "nombre": usuario["nombre"],
                "email": usuario["email"],
                "rol": usuario["rol"]
            }
            return jsonify({
                "mensaje": f"Bienvenido {usuario['nombre']}",
                "usuario": session["usuario"],
                "es_biblio": usuario["rol"] == "bibliotecario"
            })
        else:
            return jsonify({"error": "Usuario o contraseña incorrectos"}), 401
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"mensaje": "Sesión cerrada correctamente"})

@app.route("/api/registro", methods=["POST"])
@bibliotecario_required
def api_registro():
    try:
        data = request.json or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        nombre = data.get("nombre", "").strip()
        email = data.get("email", "").strip()
        if not all([username, password, nombre, email]):
            return jsonify({"error": "Todos los campos son obligatorios"}), 400
        if registrar_usuario(username, password, nombre, email, "alumno"):
            return jsonify({"mensaje": f"Alumno {nombre} registrado correctamente"})
        else:
            return jsonify({"error": "El username o email ya existen"}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al registrar usuario"}), 500

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.json or {}
        consulta = data.get("mensaje", "").strip()
        if not consulta:
            return jsonify({"error": "El mensaje está vacío"}), 400
        respuesta = procesar_consulta(consulta)
        return jsonify({"respuesta": respuesta})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route("/api/libros")
def api_libros():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    busqueda = request.args.get("busqueda", "")
    conn = get_db()
    c = conn.cursor()
    like = f"%{busqueda}%"
    if busqueda:
        c.execute("SELECT COUNT(*) FROM libros WHERE titulo ILIKE %s OR autor ILIKE %s OR categoria ILIKE %s", (like, like, like))
    else:
        c.execute("SELECT COUNT(*) FROM libros")
    total = c.fetchone()[0]
    offset = (page - 1) * per_page
    if busqueda:
        c.execute("SELECT * FROM libros WHERE titulo ILIKE %s OR autor ILIKE %s OR categoria ILIKE %s ORDER BY id DESC LIMIT %s OFFSET %s", (like, like, like, per_page, offset))
    else:
        c.execute("SELECT * FROM libros ORDER BY id DESC LIMIT %s OFFSET %s", (per_page, offset))
    libros = fetchall_as_dicts(c)
    c.close()
    conn.close()
    return jsonify({
        "libros": libros,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page)
    })

@app.route("/api/reservas", methods=["POST"])
@login_required
def crear_reserva():
    try:
        data = request.json or {}
        nombre = data.get("nombre", "")
        email = data.get("email", "")
        libro_id = data.get("libro_id") or None
        usuario_id = session["usuario"]["id"]
        if not nombre or not email:
            return jsonify({"error": "Nombre y email son obligatorios"}), 400
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO reservas (usuario_id, nombre, email, libro_id) VALUES (%s, %s, %s, %s)",
                  (usuario_id, nombre, email, libro_id))
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"mensaje": "Reserva creada correctamente"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al crear reserva"}), 500

@app.route("/api/reservas")
@bibliotecario_required
def listar_reservas():
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT r.id, r.nombre, r.email, r.fecha_reserva, r.estado,
                        l.titulo as libro_titulo, u.nombre as usuario_nombre
                 FROM reservas r
                 LEFT JOIN libros l ON r.libro_id = l.id
                 LEFT JOIN usuarios u ON r.usuario_id = u.id
                 ORDER BY r.fecha_reserva DESC""")
    reservas = fetchall_as_dicts(c)
    c.close()
    conn.close()
    return jsonify(reservas)

@app.route("/api/reservas/<int:reserva_id>/prestar", methods=["PUT"])
@bibliotecario_required
def marcar_prestado(reserva_id):
    try:
        conn = get_db()
        c = conn.cursor()
        # Traer la reserva junto con el libro_id
        c.execute("SELECT id, estado, libro_id FROM reservas WHERE id = %s", (reserva_id,))
        reserva = fetchone_as_dict(c)
        if not reserva:
            c.close(); conn.close()
            return jsonify({"error": "Reserva no encontrada"}), 404
        if reserva["estado"] != "pendiente":
            c.close(); conn.close()
            return jsonify({"error": "La reserva no está en estado pendiente"}), 400

        # Marcar la reserva como prestada
        c.execute("UPDATE reservas SET estado = 'prestado' WHERE id = %s", (reserva_id,))

        # Si la reserva tiene un libro asociado, descontar 1 del stock (sin bajar de 0)
        if reserva["libro_id"]:
            c.execute("""
                UPDATE libros
                SET disponible = GREATEST(disponible - 1, 0)
                WHERE id = %s
            """, (reserva["libro_id"],))

        # Log
        usuario = session.get("usuario", {})
        registrar_log(c, usuario.get("id"), usuario.get("nombre", "Bibliotecaria"),
                      "Reserva prestada", "reservas", reserva_id,
                      f"Reserva #{reserva_id} marcada como prestada")
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"mensaje": "Reserva marcada como prestada correctamente"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al actualizar la reserva"}), 500

@app.route("/api/reservas/<int:reserva_id>/devolver", methods=["PUT"])
@bibliotecario_required
def marcar_devuelto(reserva_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, estado, libro_id FROM reservas WHERE id = %s", (reserva_id,))
        reserva = fetchone_as_dict(c)
        if not reserva:
            c.close(); conn.close()
            return jsonify({"error": "Reserva no encontrada"}), 404
        if reserva["estado"] != "prestado":
            c.close(); conn.close()
            return jsonify({"error": "La reserva no está en estado prestado"}), 400
        # Marcar como devuelto
        c.execute("UPDATE reservas SET estado = 'devuelto' WHERE id = %s", (reserva_id,))
        # Sumar 1 al stock del libro asociado
        if reserva["libro_id"]:
            c.execute("""
                UPDATE libros
                SET disponible = disponible + 1
                WHERE id = %s
            """, (reserva["libro_id"],))
        # Log
        usuario = session.get("usuario", {})
        registrar_log(c, usuario.get("id"), usuario.get("nombre", "Bibliotecaria"),
                      "Reserva devuelta", "reservas", reserva_id,
                      f"Reserva #{reserva_id} marcada como devuelta")
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"mensaje": "Reserva marcada como devuelta correctamente"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al actualizar la reserva"}), 500

@app.route("/api/libros", methods=["POST"])
@bibliotecario_required
def agregar_libro():
    try:
        data = request.json or {}
        titulo = data.get("titulo", "").strip()
        autor = data.get("autor", "").strip()
        editorial = data.get("editorial", "").strip()
        capitulo = data.get("capitulo", "").strip()
        stock = data.get("stock", 10)
        if not titulo or not autor or not editorial:
            return jsonify({"error": "Título, autor y editorial son obligatorios"}), 400
        try:
            stock = int(stock)
            if stock < 0:
                stock = 10
        except (ValueError, TypeError):
            stock = 10
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO libros (titulo, autor, editorial, capitulo, categoria, disponible)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (titulo, autor, editorial, capitulo, "General", stock))
        # Log
        nuevo_id = None
        try:
            c.execute("SELECT id FROM libros WHERE titulo = %s AND autor = %s ORDER BY id DESC LIMIT 1", (titulo, autor))
            row = fetchone_as_dict(c)
            if row: nuevo_id = row["id"]
        except Exception: pass
        usuario = session.get("usuario", {})
        registrar_log(c, usuario.get("id"), usuario.get("nombre", "Bibliotecaria"),
                      "Agregar libro", "libros", nuevo_id,
                      f"Libro: {titulo} | Stock inicial: {stock}")
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"mensaje": f"Libro '{{titulo}}' agregado correctamente"}), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al agregar el libro"}), 500

# ═══════════════════════════════════════════════════════════
# RESEÑAS
# ═══════════════════════════════════════════════════════════
@app.route("/resenas")
def resenas_page():
    return render_template("resenas.html")

@app.route("/api/resenas", methods=["GET"])
def get_resenas():
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT id, nombre, email, picture, estrellas, comentario, fecha FROM resenas ORDER BY fecha DESC")
        rows = fetchall_as_dicts(c)
        c.close(); conn.close()
        return jsonify(rows)
    except Exception:
        traceback.print_exc()
        return jsonify([]), 500

@app.route("/api/resenas", methods=["POST"])
@login_required
def post_resena():
    try:
        data      = request.json or {}
        estrellas = int(data.get("estrellas", 0))
        comentario = data.get("comentario", "").strip()
        if not (1 <= estrellas <= 5) or not comentario:
            return jsonify({"error": "Datos inválidos"}), 400
        u = session["usuario"]
        conn = get_db(); c = conn.cursor()
        # Un usuario = una reseña (UPDATE si ya existe)
        c.execute("SELECT id FROM resenas WHERE usuario_id = %s", (u["id"],))
        existing = c.fetchone()
        if existing:
            c.execute("UPDATE resenas SET estrellas=%s, comentario=%s, picture=%s, fecha=NOW() WHERE usuario_id=%s",
                      (estrellas, comentario, u.get("picture",""), u["id"]))
        else:
            c.execute("INSERT INTO resenas (usuario_id, email, nombre, picture, estrellas, comentario) VALUES (%s,%s,%s,%s,%s,%s)",
                      (u["id"], u.get("email",""), u.get("nombre", u["username"]), u.get("picture",""), estrellas, comentario))
        conn.commit(); c.close(); conn.close()
        return jsonify({"mensaje": "Reseña guardada"})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Error al guardar la reseña"}), 500

# ═══════════════════════════════════════════════════════════
# HISTORIAL DE CHAT
# ═══════════════════════════════════════════════════════════
@app.route("/api/chat/historial", methods=["GET"])
@login_required
def get_chat_historial():
    try:
        u = session["usuario"]
        conn = get_db(); c = conn.cursor()
        # Traer sesiones únicas con su primer mensaje
        c.execute("""
            SELECT DISTINCT ON (sesion_id)
                sesion_id,
                MIN(fecha) OVER (PARTITION BY sesion_id) as inicio,
                FIRST_VALUE(mensaje) OVER (PARTITION BY sesion_id ORDER BY fecha) as primer_msg
            FROM chat_historial
            WHERE usuario_id = %s AND rol = 'user'
            ORDER BY sesion_id, inicio DESC
        """, (u["id"],))
        rows = fetchall_as_dicts(c)
        c.close(); conn.close()
        return jsonify(rows)
    except Exception:
        traceback.print_exc()
        return jsonify([]), 500

@app.route("/api/chat/historial/<sesion_id>", methods=["GET"])
@login_required
def get_chat_sesion(sesion_id):
    try:
        u = session["usuario"]
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT rol, mensaje, fecha FROM chat_historial WHERE usuario_id=%s AND sesion_id=%s ORDER BY fecha",
                  (u["id"], sesion_id))
        rows = fetchall_as_dicts(c)
        c.close(); conn.close()
        return jsonify(rows)
    except Exception:
        traceback.print_exc()
        return jsonify([]), 500

@app.route("/api/chat/guardar", methods=["POST"])
@login_required
def guardar_mensaje_chat():
    try:
        data    = request.json or {}
        sesion  = data.get("sesion_id", "")
        rol     = data.get("rol", "user")
        mensaje = data.get("mensaje", "").strip()
        if not sesion or not mensaje:
            return jsonify({"ok": False}), 400
        u = session["usuario"]
        conn = get_db(); c = conn.cursor()
        c.execute("INSERT INTO chat_historial (usuario_id, sesion_id, rol, mensaje) VALUES (%s,%s,%s,%s)",
                  (u["id"], sesion, rol, mensaje))
        conn.commit(); c.close(); conn.close()
        return jsonify({"ok": True})
    except Exception:
        traceback.print_exc()
        return jsonify({"ok": False}), 500

# ═══════════════════════════════════════════════════════════
# AVATAR
# ═══════════════════════════════════════════════════════════
@app.route("/api/avatar", methods=["PUT"])
@login_required
def set_avatar():
    try:
        data      = request.json or {}
        avatar_id = int(data.get("avatar_id", 0))
        u = session["usuario"]
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE usuarios SET avatar_id=%s WHERE id=%s", (avatar_id, u["id"]))
        conn.commit(); c.close(); conn.close()
        session["usuario"]["avatar_id"] = avatar_id
        return jsonify({"ok": True})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Error al actualizar avatar"}), 500

@app.route("/api/metricas")
@bibliotecario_required
def metricas():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM metricas")
    total = c.fetchone()[0]
    c.execute("SELECT AVG(resultados) FROM metricas")
    avg = c.fetchone()[0] or 0
    c.execute("SELECT consulta, resultados, timestamp FROM metricas ORDER BY timestamp DESC LIMIT 10")
    recientes = fetchall_as_dicts(c)
    c.execute("SELECT COUNT(*) FROM libros")
    total_libros = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM libros WHERE disponible > 0")
    disponibles = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reservas WHERE estado = 'pendiente'")
    pendientes = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'alumno'")
    total_alumnos = c.fetchone()[0]
    c.close()
    conn.close()
    return jsonify({
        "total_consultas": total,
        "promedio_resultados": round(float(avg), 2),
        "consultas_recientes": recientes,
        "total_libros": total_libros,
        "disponibles": disponibles,
        "reservas_pendientes": pendientes,
        "total_alumnos": total_alumnos
    })

@app.route("/api/metricas", methods=["DELETE"])
@bibliotecario_required
def limpiar_metricas():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM metricas")
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"mensaje": "Historial de consultas borrado correctamente"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al borrar el historial"}), 500

@app.route("/api/reservas", methods=["DELETE"])
@bibliotecario_required
def limpiar_reservas():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM reservas")
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"mensaje": "Historial de reservas borrado correctamente"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al borrar el historial"}), 500

@app.route("/api/libros/<int:libro_id>/stock", methods=["PUT"])
@bibliotecario_required
def actualizar_stock(libro_id):
    data = request.json or {}
    cantidad = data.get("cantidad")
    if cantidad is None:
        return jsonify({"error": "La cantidad es obligatoria"}), 400
    try:
        cantidad = int(cantidad)
        if cantidad < 0:
            return jsonify({"error": "La cantidad no puede ser negativa"}), 400
    except ValueError:
        return jsonify({"error": "La cantidad debe ser un número"}), 400
    conn = get_db()
    c = conn.cursor()
    # Leer stock anterior para el log
    c.execute("SELECT titulo, disponible FROM libros WHERE id = %s", (libro_id,))
    libro_prev = fetchone_as_dict(c)
    c.execute("UPDATE libros SET disponible = %s WHERE id = %s", (cantidad, libro_id))
    # Log del cambio de stock
    if libro_prev:
        usuario = session.get("usuario", {})
        registrar_log(c, usuario.get("id"), usuario.get("nombre", "Bibliotecaria"),
                      "Actualizar stock", "libros", libro_id,
                      f"Libro: {libro_prev['titulo']} | Stock: {libro_prev['disponible']} → {cantidad}")
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"mensaje": "Stock actualizado correctamente", "cantidad": cantidad})

@app.route("/api/usuarios")
@bibliotecario_required
def listar_usuarios():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, nombre, email, rol, activo, fecha_creacion FROM usuarios ORDER BY id DESC")
    usuarios = fetchall_as_dicts(c)
    c.close()
    conn.close()
    return jsonify(usuarios)

@app.route("/admin/cargar-libros")
def cargar_libros_endpoint():
    key = request.args.get("key", "")
    if key != "chacabuco2026":
        return jsonify({"error": "No autorizado"}), 403

    try:
        import pandas as pd
        import uuid
        from database import get_db

        excel_file = os.path.join(os.path.dirname(__file__), "libros.xlsx")
        if not os.path.exists(excel_file):
            return jsonify({"error": f"No se encontró libros.xlsx en el servidor"}), 404

        conn = get_db()
        c = conn.cursor()

        xl = pd.ExcelFile(excel_file)
        sheet_names = xl.sheet_names
        total = 0
        errores = 0

        for sheet_name in sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            df.columns = [col.lower().strip() for col in df.columns]
            for idx, row in df.iterrows():
                try:
                    titulo = row.get('titulo', '')
                    if pd.isna(titulo) or str(titulo).strip() == '':
                        continue
                    isbn_raw = row.get('isbn', '')
                    isbn_final = f"NO-ISBN-{uuid.uuid4().hex[:8]}" if pd.isna(isbn_raw) or str(isbn_raw).strip() == '' else str(isbn_raw).strip()
                    try:
                        c.execute("""INSERT INTO libros (titulo,capitulo,editorial,autor,categoria,descripcion,isbn,disponible,ubicacion)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (
                            str(titulo).strip(),
                            str(row.get('capitulo','')).strip() if pd.notna(row.get('capitulo')) else '',
                            str(row.get('editorial','')).strip() if pd.notna(row.get('editorial')) else '',
                            str(row.get('autor', 'Sin autor')).strip(),
                            sheet_name.strip(),
                            str(row.get('descripcion','')).strip() if pd.notna(row.get('descripcion')) else '',
                            isbn_final, 1,
                            str(row.get('ubicacion','')).strip() if pd.notna(row.get('ubicacion')) else ''))
                        total += 1
                    except Exception:
                        errores += 1
                except Exception as e:
                    errores += 1

        conn.commit()
        c.close()
        conn.close()

        return jsonify({
            "mensaje": "Carga completada",
            "libros_cargados": total,
            "errores": errores,
            "categorias": sheet_names
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/admin/estado-db")
def estado_db():
    key = request.args.get("key", "")
    if key != "chacabuco2026":
        return jsonify({"error": "No autorizado"}), 403
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM libros")
        libros = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM usuarios")
        usuarios = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reservas")
        reservas = c.fetchone()[0]
        c.close()
        conn.close()
        return jsonify({"libros": libros, "usuarios": usuarios, "reservas": reservas, "estado": "OK"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/dashboard")
@bibliotecario_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/registro")
@bibliotecario_required
def registro():
    return render_template("registro.html")

@app.route("/libros")
@bibliotecario_required
def libros():
    return render_template("libros.html")

@app.route("/checkin")
def checkin():
    return render_template("checkin.html")

@app.route("/catalogo")
@login_required
def catalogo():
    return render_template("catalogo.html")

@app.route("/api/session")
def get_session():
    if "usuario" in session:
        return jsonify({
            "logged_in": True,
            "usuario": session["usuario"],
            "es_biblio": session["usuario"]["rol"] == "bibliotecario"
        })
    return jsonify({"logged_in": False})

@app.route("/landing")
def landing():
    return render_template("landing.html")

@app.route("/mis-prestamos")
@login_required
def mis_prestamos():
    return render_template("mis_prestamos.html")

@app.route("/api/mis-prestamos")
@login_required
def api_mis_prestamos():
    try:
        u = session["usuario"]
        conn = get_db(); c = conn.cursor()
        c.execute("""
            SELECT r.id, l.titulo, l.autor, l.categoria, r.estado, r.fecha_reserva as fecha
            FROM reservas r
            JOIN libros l ON r.libro_id = l.id
            WHERE r.usuario_id = %s
            ORDER BY r.fecha_reserva DESC
        """, (u["id"],))
        rows = fetchall_as_dicts(c)
        c.close(); conn.close()
        return jsonify(rows)
    except Exception:
        traceback.print_exc()
        return jsonify([]), 500

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    print("🚀 Iniciando Biblioteca IA")
    print("📝 Usuario Bibliotecaria: biblio / biblio123")
    app.run(debug=False, host="0.0.0.0", port=5000)

# ─────────────────────────────────────────────────────────────
# ELIMINAR LIBRO
# ─────────────────────────────────────────────────────────────
@app.route("/api/libros/<int:libro_id>", methods=["DELETE"])
@bibliotecario_required
def eliminar_libro(libro_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT titulo FROM libros WHERE id = %s", (libro_id,))
        libro = fetchone_as_dict(c)
        if not libro:
            c.close(); conn.close()
            return jsonify({"error": "Libro no encontrado"}), 404
        # Eliminar reservas asociadas primero (FK)
        c.execute("DELETE FROM reservas WHERE libro_id = %s", (libro_id,))
        c.execute("DELETE FROM libros WHERE id = %s", (libro_id,))
        # Registrar en logs_actividad si existe la tabla
        try:
            usuario = session.get("usuario", {})
            c.execute("""INSERT INTO logs_actividad (usuario_id, usuario_nombre, accion, tabla_afectada, registro_id, detalles)
                         VALUES (%s, %s, %s, %s, %s, %s)""",
                      (usuario.get("id"), usuario.get("nombre", "Bibliotecaria"),
                       "Eliminar libro", "libros", libro_id,
                       "Libro eliminado: " + libro["titulo"]))
        except Exception:
            pass
        conn.commit()
        c.close(); conn.close()
        return jsonify({"mensaje": "Libro eliminado correctamente"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al eliminar el libro"}), 500


@app.route("/logs")
@admin_required
def admin_logs():
    return render_template("admin_logs.html")

@app.route("/api/admin/logs")
@admin_required
def api_admin_logs():
    try:
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("""SELECT id, timestamp, usuario_nombre, accion, tabla_afectada, registro_id, detalles
                         FROM logs_actividad ORDER BY timestamp DESC LIMIT 200""")
            logs = fetchall_as_dicts(c)
        except Exception:
            logs = []
        c.close()
        conn.close()
        return jsonify(logs)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500