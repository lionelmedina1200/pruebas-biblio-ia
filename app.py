import os
import traceback
from flask import Flask, render_template, request, jsonify, session
from database import init_db, get_db, verificar_usuario, registrar_usuario, fetchall_as_dicts, fetchone_as_dict
from ai_engine import procesar_consulta
from auth import login_required, bibliotecario_required


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
app.secret_key = "biblioteca_secreta_segura_2026_cambiame"

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


# ─────────────────────────────────────────────────────────────
# SESIÓN ADMIN — logs de stock y reservas
# ─────────────────────────────────────────────────────────────
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin2026")

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            from flask import redirect
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    from flask import request as req
    error = ""
    if req.method == "POST":
        pw = req.form.get("password", "")
        if pw == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return app.redirect("/admin/logs")
        error = "Contraseña incorrecta"
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>Admin Login</title>
<link rel="stylesheet" href="/static/css/style.css">
<style>body{{display:flex;align-items:center;justify-content:center;min-height:100vh;}}
.login-box{{background:var(--bg-card);padding:2.5rem;border-radius:var(--radius);border:1px solid var(--border);max-width:360px;width:100%;box-shadow:0 12px 40px rgba(0,0,0,.5);}}
h2{{color:var(--azul-claro);margin-bottom:1.5rem;text-align:center;}}
.err{{color:#f87171;margin-bottom:1rem;text-align:center;font-weight:600;}}
</style></head><body>
<div class="login-box">
  <h2>🔐 Acceso Admin</h2>
  {"<p class='err'>⚠️ " + error + "</p>" if error else ""}
  <form method="POST">
    <div class="form-group">
      <label>Contraseña de administrador</label>
      <input type="password" name="password" class="form-input" autofocus placeholder="Contraseña admin">
    </div>
    <button type="submit" class="btn-primary" style="width:100%;margin-top:.5rem;">Ingresar</button>
  </form>
  <p style="text-align:center;margin-top:1rem;"><a href="/" style="color:var(--text-muted);font-size:.85rem;">← Volver al inicio</a></p>
</div></body></html>"""

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    from flask import redirect
    return redirect("/admin/login")

@app.route("/admin/logs")
@admin_required
def admin_logs():
    return render_template("admin_logs.html")

@app.route("/api/admin/logs")
def api_admin_logs():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "No autorizado"}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        # Intentar leer tabla logs_actividad
        try:
            c.execute("""SELECT id, timestamp, usuario_nombre, accion, tabla_afectada, registro_id, detalles
                         FROM logs_actividad ORDER BY timestamp DESC LIMIT 200""")
            logs = fetchall_as_dicts(c)
        except Exception:
            logs = []
        c.close(); conn.close()
        return jsonify(logs)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500