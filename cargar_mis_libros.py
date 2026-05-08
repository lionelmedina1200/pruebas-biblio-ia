import pg8000
import pg8000.native
import pandas as pd
from werkzeug.security import generate_password_hash
import os
import uuid
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.ndskqxfsufsglbqmdjfh:Github_SupaBase@aws-1-us-west-1.pooler.supabase.com:6543/postgres")

def parse_db_url(url):
    r = urlparse(url)
    return {"host": r.hostname, "port": r.port or 5432, "database": r.path.lstrip("/"), "user": r.username, "password": r.password}

def cargar_libros(excel_file='libros.xlsx'):
    if not os.path.exists(excel_file):
        print(f"❌ ERROR: No encontré '{excel_file}'")
        return

    params = parse_db_url(DATABASE_URL)
    conn = pg8000.connect(**params, ssl_context=True)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS libros (
        id SERIAL PRIMARY KEY, titulo TEXT NOT NULL, capitulo TEXT, editorial TEXT,
        autor TEXT NOT NULL, categoria TEXT NOT NULL, descripcion TEXT,
        isbn TEXT UNIQUE, disponible INTEGER DEFAULT 1, ubicacion TEXT,
        fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
        nombre TEXT NOT NULL, email TEXT UNIQUE NOT NULL, rol TEXT DEFAULT 'alumno',
        activo INTEGER DEFAULT 1, fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    hashed_pw = generate_password_hash("biblio123", method='pbkdf2:sha256')
    try:
        c.execute("INSERT INTO usuarios (username, password, nombre, email, rol) VALUES (%s,%s,%s,%s,%s)",
                  ("biblio", hashed_pw, "Bibliotecaria", "biblio@biblioteca.com", "bibliotecario"))
    except Exception:
        pass
    conn.commit()

    xl = pd.ExcelFile(excel_file)
    total = 0
    for sheet_name in xl.sheet_names:
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
                        str(row.get('autor','')).strip(),
                        sheet_name.strip(),
                        str(row.get('descripcion','')).strip() if pd.notna(row.get('descripcion')) else '',
                        isbn_final, 1,
                        str(row.get('ubicacion','')).strip() if pd.notna(row.get('ubicacion')) else ''))
                    total += 1
                except Exception:
                    pass
            except Exception as e:
                print(f"Fila {idx}: {e}")
    conn.commit()
    c.close()
    conn.close()
    print(f"✅ Carga completada: {total} libros cargados a Supabase")

if __name__ == "__main__":
    cargar_libros()