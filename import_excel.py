import psycopg2
import psycopg2.extras
import pandas as pd
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:Github_SupaBase@db.ndskqxfsufsglbqmdjfh.supabase.co:5432/postgres")

def importar_excel_a_libros(archivo_excel):
    if not os.path.exists(archivo_excel):
        print(f"❌ ERROR: No se encuentra el archivo '{archivo_excel}'.")
        return False

    try:
        print(f"📖 Leyendo archivo: {archivo_excel}...")
        df = pd.read_excel(archivo_excel)

        columnas_requeridas = ["titulo", "autor", "categoria"]
        for col in columnas_requeridas:
            if col not in df.columns:
                print(f"❌ ERROR: Falta la columna '{col}' en el Excel.")
                return False

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        c = conn.cursor()

        print("🛠️  Verificando estructura de la base de datos...")
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
        conn.commit()

        print("📥 Insertando libros...")
        insertados = 0
        errores = 0

        for index, row in df.iterrows():
            try:
                titulo = row.get("titulo")
                if pd.isna(titulo) or str(titulo).strip() == "":
                    continue

                c.execute("""
                    INSERT INTO libros
                    (titulo, capitulo, editorial, autor, categoria, descripcion, isbn, disponible, ubicacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (isbn) DO NOTHING
                """, (
                    str(titulo).strip(),
                    str(row.get("capitulo", "") or "").strip(),
                    str(row.get("editorial", "") or "").strip(),
                    str(row.get("autor", "") or "").strip(),
                    str(row.get("categoria", "") or "").strip(),
                    str(row.get("descripcion", "") or "").strip(),
                    str(row.get("isbn", "") or "").strip() or None,
                    1,
                    str(row.get("ubicacion", "") or "").strip()
                ))
                insertados += 1
            except Exception as e:
                print(f"⚠️ Error en fila {index}: {e}")
                errores += 1

        conn.commit()
        c.close()
        conn.close()

        print(f"\n✅ Importación terminada exitosamente:")
        print(f"   📚 Libros insertados: {insertados}")
        print(f"   ⚠️ Errores ignorados: {errores}")
        return True

    except Exception as e:
        print(f"❌ Error fatal al importar: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python import_excel.py <archivo.xlsx>")
        print("Ejemplo: python import_excel.py libros.xlsx")
    else:
        importar_excel_a_libros(sys.argv[1])