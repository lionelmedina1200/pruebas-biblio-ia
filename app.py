from flask import Flask, render_template, request, jsonify, session
from database import init_db, get_db, verificar_usuario, registrar_usuario
from ai_engine import procesar_consulta
from auth import login_required, bibliotecario_required, es_bibliotecario
import traceback

app = Flask(__name__)
app.secret_key = "biblioteca_secreta_segura_2026_cambiame"

@app.before_request
def setup_db():
    init_db()

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

    total = c.fetchone()["count"]
    offset = (page - 1) * per_page

    if busqueda:
        c.execute("""SELECT * FROM libros WHERE titulo ILIKE %s OR autor ILIKE %s OR categoria ILIKE %s
                     ORDER BY id DESC LIMIT %s OFFSET %s""", (like, like, like, per_page, offset))
    else:
        c.execute("SELECT * FROM libros ORDER BY id DESC LIMIT %s OFFSET %s", (per_page, offset))

    libros = [dict(row) for row in c.fetchall()]
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
        libro_id = data.get("libro_id")
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
    c.execute("""SELECT r.*, l.titulo as libro_titulo, u.nombre as usuario_nombre
                 FROM reservas r
                 LEFT JOIN libros l ON r.libro_id = l.id
                 LEFT JOIN usuarios u ON r.usuario_id = u.id
                 ORDER BY r.fecha_reserva DESC""")
    reservas = [dict(row) for row in c.fetchall()]
    c.close()
    conn.close()
    return jsonify(reservas)

@app.route("/api/reservas/<int:reserva_id>/prestar", methods=["PUT"])
@bibliotecario_required
def marcar_prestado(reserva_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, estado FROM reservas WHERE id = %s", (reserva_id,))
        reserva = c.fetchone()
        if not reserva:
            c.close()
            conn.close()
            return jsonify({"error": "Reserva no encontrada"}), 404
        if reserva["estado"] != "pendiente":
            c.close()
            conn.close()
            return jsonify({"error": "La reserva no está en estado pendiente"}), 400
        c.execute("UPDATE reservas SET estado = 'prestado' WHERE id = %s", (reserva_id,))
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"mensaje": "Reserva marcada como prestada correctamente"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error al actualizar la reserva"}), 500

@app.route("/api/metricas")
@bibliotecario_required
def metricas():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM metricas")
    total = c.fetchone()["count"]
    c.execute("SELECT AVG(resultados) FROM metricas")
    avg = c.fetchone()["avg"] or 0
    c.execute("SELECT consulta, resultados, timestamp FROM metricas ORDER BY timestamp DESC LIMIT 10")
    recientes = [dict(row) for row in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM libros")
    total_libros = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) FROM libros WHERE disponible > 0")
    disponibles = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) FROM reservas WHERE estado = 'pendiente'")
    pendientes = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'alumno'")
    total_alumnos = c.fetchone()["count"]
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
    c.execute("UPDATE libros SET disponible = %s WHERE id = %s", (cantidad, libro_id))
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
    usuarios = [dict(row) for row in c.fetchall()]
    c.close()
    conn.close()
    return jsonify(usuarios)

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

if __name__ == "__main__":
    print("🚀 Iniciando Biblioteca IA")
    print("📝 Usuario Bibliotecaria: biblio / biblio123")
    app.run(debug=False, host="0.0.0.0", port=5000)