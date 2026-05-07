import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "biblioteca.db")

try:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM libros")
    total = c.fetchone()[0]
    print(f"📚 Total de libros en la BD: {total}")
    if total > 0:
        c.execute("SELECT titulo, autor, categoria FROM libros LIMIT 5")
        libros = c.fetchall()
        print("\n📖 Primeros 5 libros:")
        for l in libros:
            print(f"   - {l['titulo']} ({l['autor']}) - Categoría: {l['categoria']}")
    else:
        print("⚠️  La base de datos está VACÍA. Ejecutá: python cargar_mis_libros.py")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")