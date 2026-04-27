import pandas as pd
import sqlite3
import os

DB_PATH = "biblioteca.db"

def importar_excel_a_libros(archivo_excel):
    """
    Importa libros desde un Excel a la base de datos.
    
    El Excel debe tener las columnas:
    - titulo (obligatorio)
    - capitulo (opcional)
    - editorial (opcional)
    - autor (obligatorio)
    - categoria (obligatorio)
    - descripcion (opcional)
    - isbn (opcional)
    - ubicacion (opcional)
    """
    if not os.path.exists(archivo_excel):
        print(f"❌ El archivo {archivo_excel} no existe")
        return False
    
    try:
        df = pd.read_excel(archivo_excel)
        
        columnas_requeridas = ["titulo", "autor", "categoria"]
        for col in columnas_requeridas:
            if col not in df.columns:
                print(f"❌ La columna '{col}' es requerida en el Excel")
                return False
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        insertados = 0
        errores = 0
        
        for index, row in df.iterrows():
            try:
                c.execute("""
                    INSERT OR IGNORE INTO libros 
                    (titulo, capitulo, editorial, autor, categoria, descripcion, isbn, disponible, ubicacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["titulo"],
                    row.get("capitulo", ""),
                    row.get("editorial", ""),
                    row["autor"],
                    row["categoria"],
                    row.get("descripcion", ""),
                    row.get("isbn", ""),
                    1,
                    row.get("ubicacion", "")
                ))
                insertados += 1
            except Exception as e:
                print(f"⚠️ Error en fila {index}: {e}")
                errores += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Importación completada:")
        print(f"   📚 Libros insertados: {insertados}")
        print(f"   ⚠️ Errores: {errores}")
        return True
        
    except Exception as e:
        print(f"❌ Error al importar: {e}")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python import_excel.py <archivo.xlsx>")
        print("Ejemplo: python import_excel.py libros.xlsx")
    else:
        importar_excel_a_libros(sys.argv[1])
