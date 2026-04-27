import sqlite3
import pandas as pd
from werkzeug.security import generate_password_hash
import os
import uuid

print("🚀 Iniciando carga de libros desde Excel...")

# Conectar a la BD
if os.path.exists('biblioteca.db'):
    os.remove('biblioteca.db') # Borramos la vieja para empezar limpio
    print("🗑️ Base de datos anterior eliminada.")

conn = sqlite3.connect('biblioteca.db')
c = conn.cursor()

# Crear tablas
print("📋 Creando tablas...")
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

# Crear usuario bibliotecaria
print("👤 Creando usuario bibliotecaria...")
hashed_pw = generate_password_hash("biblio123", method='pbkdf2:sha256')
c.execute("""INSERT OR IGNORE INTO usuarios (username, password, nombre, email, rol) 
             VALUES (?, ?, ?, ?, ?)""",
          ("biblio", hashed_pw, "Bibliotecaria", "biblio@biblioteca.com", "bibliotecario"))
conn.commit()

# Leer Excel
excel_file = 'libros.xlsx'
if not os.path.exists(excel_file):
    print(f"❌ ERROR: No encontré '{excel_file}'")
    conn.close()
    exit()

print(f"📖 Leyendo {excel_file}...")

try:
    xl = pd.ExcelFile(excel_file)
    sheet_names = xl.sheet_names
    
    print(f"📑 Encontradas {len(sheet_names)} categorías: {', '.join(sheet_names)}")
    
    total_libros = 0
    
    for sheet_name in sheet_names:
        print(f"\n📚 Procesando categoría: '{sheet_name}'")
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        
        # Normalizar columnas
        df.columns = [col.lower().strip() for col in df.columns]
        libros_insertados = 0
        
        for idx, row in df.iterrows():
            try:
                titulo = row.get('titulo', '')
                autor = row.get('autor', '')
                
                if pd.isna(titulo) or str(titulo).strip() == '': continue # Saltar filas vacías

                # --- AQUÍ ESTÁ LA CORRECCIÓN ---
                # Si el ISBN está vacío o es NaN, le inventamos uno único para que no choque
                isbn_raw = row.get('isbn', '')
                if pd.isna(isbn_raw) or str(isbn_raw).strip() == '':
                    isbn_final = f"NO-ISBN-{uuid.uuid4().hex[:8]}" # Genera un código único
                else:
                    isbn_final = str(isbn_raw).strip()
                # --------------------------------

                c.execute("""
                    INSERT OR IGNORE INTO libros 
                    (titulo, capitulo, editorial, autor, categoria, descripcion, isbn, disponible, ubicacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        
        print(f"  ✅ {libros_insertados} libros insertados")
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
    conn.close()