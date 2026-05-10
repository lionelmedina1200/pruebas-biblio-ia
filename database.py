import os
import pg8000
import pg8000.native
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.ndskqxfsufsglbqmdjfh:Github_SupaBase@aws-1-us-west-1.pooler.supabase.com:6543/postgres")

def parse_db_url(url):
    r = urlparse(url)
    return {
        "host": r.hostname,
        "port": r.port or 5432,
        "database": r.path.lstrip("/"),
        "user": r.username,
        "password": r.password,
    }

def get_db():
    params = parse_db_url(DATABASE_URL)
    conn = pg8000.connect(
        host=params["host"],
        port=params["port"],
        database=params["database"],
        user=params["user"],
        password=params["password"],
        ssl_context=True
    )
    return conn

def fetchall_as_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def fetchone_as_dict(cursor):
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row)) if row else None

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

    # Migración: agregar google_id si la tabla ya existe sin esa columna
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE")
    except Exception:
        pass

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

    c.execute("""CREATE TABLE IF NOT EXISTS resenas (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        nombre TEXT NOT NULL,
        picture TEXT DEFAULT '',
        estrellas INTEGER NOT NULL CHECK (estrellas BETWEEN 1 AND 5),
        comentario TEXT NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # Migración: agregar picture si no existe aún
    try:
        c.execute("ALTER TABLE resenas ADD COLUMN IF NOT EXISTS picture TEXT DEFAULT ''")
    except Exception:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS chat_historial (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        sesion_id TEXT NOT NULL,
        rol TEXT NOT NULL,
        mensaje TEXT NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Migrar avatar_id a usuarios si no existe
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS avatar_id INTEGER DEFAULT 0")
    except Exception:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS logs_actividad (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        usuario_id INTEGER,
        usuario_nombre TEXT,
        accion TEXT NOT NULL,
        tabla_afectada TEXT,
        registro_id INTEGER,
        detalles TEXT
    )""")

    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'bibliotecario'")
    count = c.fetchone()[0]
    if count == 0:
        hashed_pw = generate_password_hash("biblio123", method='pbkdf2:sha256')
        c.execute("""INSERT INTO usuarios (username, password, nombre, email, rol)
                     VALUES (%s, %s, %s, %s, %s)""",
                  ("biblio", hashed_pw, "Bibliotecaria", "biblio@biblioteca.com", "bibliotecario"))

    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'admin'")
    count_admin = c.fetchone()[0]
    if count_admin == 0:
        hashed_pw_admin = generate_password_hash("admin2026", method='pbkdf2:sha256')
        c.execute("""INSERT INTO usuarios (username, password, nombre, email, rol)
                     VALUES (%s, %s, %s, %s, %s)""",
                  ("admin", hashed_pw_admin, "Administrador", "admin@biblioteca.com", "admin"))

    conn.commit()
    c.close()
    conn.close()

def verificar_usuario(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE username = %s AND activo = 1", (username,))
    usuario = fetchone_as_dict(c)
    c.close()
    conn.close()
    if usuario and check_password_hash(usuario["password"], password):
        return usuario
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
    except Exception:
        return False