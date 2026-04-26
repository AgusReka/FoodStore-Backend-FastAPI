# Comando para crear el entorno
python -m venv venv
# Comando para activar el entorno
venv\Scripts\activate
# Comando para instalar dependencias
pip install -r requirements.txt
# Comando para iniciarlo
uvicorn app.main:app --reload