#!/bin/bash
echo "🚀 Configurando Biblioteca IA..."
pip install -r requirements.txt
python database.py
echo "✅ Todo listo. Ejecutá: python app.py"
echo "💡 Recordá configurar tu API KEY:"
echo "   export AQ.Ab8RN6JJb31M3GYKu-fef-MmnnksxYzCpbP0UagON1Cs6R5_jg  (Linux/Mac)"
echo "   set AQ.Ab8RN6JJb31M3GYKu-fef-MmnnksxYzCpbP0UagON1Cs6R5_jg  (Windows CMD)"