from pathlib import Path

# Las rutas no dependen de la carpeta desde la que se lanza Streamlit.
DIRECTORIO = Path(__file__).resolve().parent
CORPUS_PATH = DIRECTORIO / "corpus"
CHROMA_DB_PATH = DIRECTORIO / "chroma_db"
COLLECTION_NAME = "ciberseguridad"
EMBEDDING_MODEL = "gemini-embedding-001"
MODELOS = ["gemini-flash-latest", "gemini-pro-latest"]
TEMPERATURE = 0.1
SEARCH_K = 2

# Parámetros utilizados al reconstruir la base documental.
CHUNK_SIZE = 5000
CHUNK_OVERLAP = 1000
