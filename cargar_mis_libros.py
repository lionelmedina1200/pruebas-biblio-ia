import psycopg2
import psycopg2.extras
import pandas as pd
from werkzeug.security import generate_password_hash
import os
import uuid

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:Github_SupaBase@db.ndskqxfsufsglbqmdjfh.supabase.co:5432/postgres")

print("🚀 Iniciando carga de libros desde Excel a Supabase (PostgreSQL)...")

def cargar_libros(excel_file='libros.xlsx'):
    if not os.path.exists(excel_file):
        print(f"❌ ERROR: No encontré '{excel_file}'")
        return

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    c = conn.cursor()

    print("📋 Creando tablas si no existen...")

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

    c.execute("""CREATE TABLE IF NOT EXISTS reservas (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER REFERENCES usuarios(id),
        nombre TEXT NOT NULL,
        email TEXT NOT NULL,
        libro_id INTEGER REFERENCES libros(id),
        fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        estado TEXT DEFAULT 'pendiente'
    )""")

    print("👤 Creando usuario bibliotecaria si no existe...")
    hashed_pw = generate_password_hash("biblio123", method='pbkdf2:sha256')
    c.execute("""INSERT INTO usuarios (username, password, nombre, email, rol)
                 VALUES (%s, %s, %s, %s, %s)
                 ON CONFLICT (username) DO NOTHING""",
              ("biblio", hashed_pw, "Bibliotecaria", "biblio@biblioteca.com", "bibliotecario"))
    conn.commit()

    print(f"📖 Leyendo {excel_file}...")
    try:
        xl = pd.ExcelFile(excel_file)
        sheet_names = xl.sheet_names
        print(f"📑 Encontradas {len(sheet_names)} categorías: {', '.join(sheet_names)}")

        total_libros = 0

        for sheet_name in sheet_names:
            print(f"\n📚 Procesando categoría: '{sheet_name}'")
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            df.columns = [col.lower().strip() for col in df.columns]
            libros_insertados = 0

            for idx, row in df.iterrows():
                try:
                    titulo = row.get('titulo', '')
                    autor = row.get('autor', '')

                    if pd.isna(titulo) or str(titulo).strip() == '':
                        continue

                    isbn_raw = row.get('isbn', '')
                    if pd.isna(isbn_raw) or str(isbn_raw).strip() == '':
                        isbn_final = f"NO-ISBN-{uuid.uuid4().hex[:8]}"
                    else:
                        isbn_final = str(isbn_raw).strip()

                    c.execute("""
                        INSERT INTO libros
                        (titulo, capitulo, editorial, autor, categoria, descripcion, isbn, disponible, ubicacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (isbn) DO NOTHING
                    """, (
                        str(titulo).strip(),
                        str(row.get('capitulo', '')).strip() if pd.notna(row.get('capitulo')) else '',
                        str(row.get('editorial', '')).strip() if pd.notna(row.get('editorial')) else '',
                        str(autor).strip(),
                        sheet_name.strip(),
                        str(row.get('descripcion', '')).strip() if pd.notna(row.get('descripcion')) else '',
                        isbn_final,
                        1,
                        str(row.get('ubicacion', '')).strip() if pd.notna(row.get('ubicacion')) else ''
                    ))
                    libros_insertados += 1

                except Exception as e:
                    print(f"  ⚠️  Fila {idx}: Error -> {e}")

            print(f"  ✅ {libros_insertados} libros procesados")
            total_libros += libros_insertados

        conn.commit()
        print(f"\n{'='*50}")
        print(f"✅ ¡Carga COMPLETADA!")
        print(f"📚 Total libros cargados: {total_libros}")
        print(f"{'='*50}")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    cargar_libros()