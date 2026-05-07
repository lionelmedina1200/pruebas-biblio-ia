import pandas as pd
import sqlite3
import os

# Usamos la misma ruta que database.py para asegurar que es el mismo archivo
DB_PATH = os.path.join(os.path.dirname(__file__), "biblioteca.db")

def importar_excel_a_libros(archivo_excel):
    """
    Importa libros desde un Excel a la base de datos SQLite.
    """
    # 1. Verificar que el Excel exista
    if not os.path.exists(archivo_excel):
        print(f"❌ ERROR: No se encuentra el archivo '{archivo_excel}'.")
        print("   Asegurate de que el archivo esté en la misma carpeta que este script.")
        return False
    
    try:
        print(f"📖 Leyendo archivo: {archivo_excel}...")
        df = pd.read_excel(archivo_excel)
        
        # 2. Verificar columnas obligatorias
        columnas_requeridas = ["titulo", "autor", "categoria"]
        for col in columnas_requeridas:
            if col not in df.columns:
                print(f" ERROR: Falta la columna '{col}' en el Excel.")
                return False
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 3. CRÍTICO: Crear la tabla SI NO EXISTE
        # Esto evita el error si la app no corrió antes
        print("🛠️  Verificando estructura de la base de datos...")
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
        conn.commit() # Guardar la creación de la tabla
        
        print("📥 Insertando libros...")
        insertados = 0
        errores = 0
        
        for index, row in df.iterrows():
            try:
                # Validar que tenga título
                titulo = row.get("titulo")
                if pd.isna(titulo) or str(titulo).strip() == "":
                    continue

                # Insertar con conversión a string para evitar errores de tipos
                c.execute("""
                    INSERT OR IGNORE INTO libros 
                    (titulo, capitulo, editorial, autor, categoria, descripcion, isbn, disponible, ubicacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(titulo).strip(),
                    str(row.get("capitulo", "") or "").strip(),
                    str(row.get("editorial", "") or "").strip(),
                    str(row.get("autor", "") or "").strip(),
                    str(row.get("categoria", "") or "").strip(),
                    str(row.get("descripcion", "") or "").strip(),
                    str(row.get("isbn", "") or "").strip(),
                    1,
                    str(row.get("ubicacion", "") or "").strip()
                ))
                insertados += 1
            except Exception as e:
                print(f"⚠️ Error en fila {index}: {e}")
                errores += 1
        
        conn.commit()
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