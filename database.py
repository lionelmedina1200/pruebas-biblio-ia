import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "biblioteca.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Tabla de usuarios con roles UNIFICADOS
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        nombre TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        rol TEXT DEFAULT 'alumno',
        activo INTEGER DEFAULT 1,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Tabla de libros
    c.execute("""CREATE TABLE IF NOT EXISTS libros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        capitulo TEXT,
        editorial TEXT,
        autor TEXT NOT NULL,
        categoria TEXT NOT NULL,
        descripcion TEXT,
        isbn TEXT UNIQUE,
        disponible INTEGER DEFAULT 1,
        ubicacion TEXT,
        fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS reservas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        nombre TEXT NOT NULL,
        email TEXT NOT NULL,
        libro_id INTEGER,
        fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        estado TEXT DEFAULT 'pendiente',
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY (libro_id) REFERENCES libros(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS metricas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consulta TEXT,
        resultados INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Crear bibliotecario (UNICO ROL con todos los permisos)
    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'bibliotecario'")
    if c.fetchone()[0] == 0:
        hashed_pw = generate_password_hash("biblio123", method='pbkdf2:sha256')
        c.execute("""INSERT INTO usuarios (username, password, nombre, email, rol) 
                     VALUES (?, ?, ?, ?, ?)""",
                  ("biblio", hashed_pw, "Bibliotecaria", "biblio@biblioteca.com", "bibliotecario"))

    # ✅ LIBROS DE EJEMPLO ELIMINADOS - Solo se crea la estructura, no se insertan datos

    conn.commit()
    conn.close()

def verificar_usuario(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE username = ? AND activo = 1", (username,))
    usuario = c.fetchone()
    conn.close()
    
    if usuario and check_password_hash(usuario["password"], password):
        return dict(usuario)
    return None

def registrar_usuario(username, password, nombre, email, rol="alumno"):
    try:
        conn = get_db()
        c = conn.cursor()
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        c.execute("""INSERT INTO usuarios (username, password, nombre, email, rol) 
                     VALUES (?, ?, ?, ?, ?)""",
                  (username, hashed_pw, nombre, email, rol))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

if __name__ == "__main__":
    init_db()
    print("✅ Base de datos inicializada correctamente.")
    print("📝 Usuario Bibliotecaria: biblio / biblio123")