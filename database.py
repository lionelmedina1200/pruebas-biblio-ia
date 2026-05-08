import os
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:Github_SupaBase@db.ndskqxfsufsglbqmdjfh.supabase.co:5432/postgres")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        nombre TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        rol TEXT DEFAULT 'alumno',
        activo INTEGER DEFAULT 1,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS libros (
        id SERIAL PRIMARY KEY,
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
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER REFERENCES usuarios(id),
        nombre TEXT NOT NULL,
        email TEXT NOT NULL,
        libro_id INTEGER REFERENCES libros(id),
        fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        estado TEXT DEFAULT 'pendiente'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS metricas (
        id SERIAL PRIMARY KEY,
        consulta TEXT,
        resultados INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Crear usuario bibliotecario si no existe
    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol = %s", ('bibliotecario',))
    resultado = c.fetchone()
    count = resultado['count'] if resultado else 0
    if count == 0:
        hashed_pw = generate_password_hash("biblio123", method='pbkdf2:sha256')
        c.execute("""INSERT INTO usuarios (username, password, nombre, email, rol)
                     VALUES (%s, %s, %s, %s, %s)""",
                  ("biblio", hashed_pw, "Bibliotecaria", "biblio@biblioteca.com", "bibliotecario"))

    conn.commit()
    c.close()
    conn.close()

def verificar_usuario(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE username = %s AND activo = 1", (username,))
    usuario = c.fetchone()
    c.close()
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
        VALUES (%s, %s, %s, %s, %s)""",
        (username, hashed_pw, nombre, email, rol))
        conn.commit()
        c.close()
        conn.close()
        return True
    except psycopg2.IntegrityError:
        return False