from functools import wraps
from flask import session, redirect, url_for, jsonify

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            return jsonify({"error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated_function

def bibliotecario_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            return jsonify({"error": "No autorizado"}), 401
        if session["usuario"]["rol"] != "bibliotecario":
            return jsonify({"error": "Se requiere rol de bibliotecario"}), 403
        return f(*args, **kwargs)
    return decorated_function

def get_usuario_actual():
    return session.get("usuario")

def es_bibliotecario():
    usuario = session.get("usuario")
    return usuario and usuario["rol"] == "bibliotecario"