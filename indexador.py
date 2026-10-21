import os
from getpass import getpass

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from chromadb import PersistentClient

from config import CORPUS_PATH, CHROMA_DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL, \
    CHUNK_SIZE, CHUNK_OVERLAP


def indexar():
    # La variable de entorno es opcional; si falta, pedimos la clave sin mostrarla.
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        api_key = getpass("Introduce tu API key de Google (entrada oculta): ").strip()
    if not api_key:
        raise ValueError("La API key no puede estar vacía. No se ha modificado la base.")
    # 1. Cargamos todos los PDF del corpus, ordenados por nombre.
    archivos = sorted(
        archivo for archivo in CORPUS_PATH.iterdir()
        if archivo.is_file() and archivo.suffix.lower() == ".pdf")
    if not archivos:
        raise ValueError(f"No hay documentos PDF en {CORPUS_PATH}")

    paginas = []
    for archivo in archivos:
        loader = PyPDFLoader(str(archivo))
        # Cada página es un Document: page_content contiene el texto y
        # metadata que incluye su procedencia (source) y su página (page, desde 0).
        paginas_pdf = loader.load()
        # Guardamos solo el nombre del PDF, sin la ruta del equipo.
        for pagina in paginas_pdf:
            pagina.metadata["source"] = archivo.name
        paginas.extend(paginas_pdf)
        print(f"{archivo.name}: {len(paginas_pdf)} páginas")

    # 2. Fragmentamos conservando los metadatos de cada página del PDF.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,  # Posición del fragmento dentro del texto de su página.
    )
    
    # Conservamos solo fragmentos con texto; strip() permite detectar los que
    # contienen únicamente espacios o saltos de línea, sin modificar los demás.
    chunks = text_splitter.split_documents(paginas)
    chunks = [chunk for chunk in chunks if chunk.page_content.strip()]
    if not chunks:
        raise ValueError("Los PDF no contienen texto extraíble para indexar.")
    print(f"Fragmentos generados: {len(chunks)}")

    # 3. Configuramos Gemini para indexar documentos.
    # Aquí todavía no calculamos vectores: indicamos qué modelo se utilizará.
    modelo_embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
        task_type="RETRIEVAL_DOCUMENT")

    # 4. Instanciamos el cliente y borramos TODAS las colecciones de la base de datos local.
    cliente = PersistentClient(path=str(CHROMA_DB_PATH))
    for coleccion in cliente.list_collections():
        cliente.delete_collection(name=coleccion.name)
    print("Base de datos documental vaciada.")

    # Creamos la colección y el objeto de LangChain para trabajar con ella.
    # Asociamos el modelo de embeddings, pero aún no insertamos fragmentos.
    base_datos = Chroma(
        client=cliente,
        collection_name=COLLECTION_NAME,
        embedding_function=modelo_embeddings,
        persist_directory=str(CHROMA_DB_PATH))

    # 5. Indexamos en lotes de 32 fragmentos
    for inicio in range(0, len(chunks), 32):
        lote = chunks[inicio:inicio + 32]
        # add_documents() extrae los textos y calcula sus embeddings con Gemini.
        # Guarda cada texto, su vector y sus metadatos asociados a un ID.
        base_datos.add_documents(lote)
        print(f"Indexados: {min(inicio + 32, len(chunks))}/{len(chunks)}")

    print(f"Base de datos guardada ...")

    # 6. Leemos lo almacenado en la base de datos para verificar que se indexó correctamente.
    datos = base_datos.get(include=["documents", "metadatas", "embeddings"])

    for numero, (identificador, texto, metadatos, vector) in enumerate(
        zip(datos["ids"], datos["documents"], datos["metadatas"], datos["embeddings"]),
        start=1):
        pagina = metadatos.get("page", "desconocida")
        if isinstance(pagina, int):
            pagina += 1  # Mostramos las páginas desde 1, aunque se guardan desde 0.
        contenido = texto[:100].replace("\n", " ")

        print(f"\n--- Chunk {numero}")
        print(f"Identificador: {identificador}")
        print(f"Fuente: {metadatos.get('source', 'desconocida')}")
        print(f"Página: {pagina}")
        print(f"Contenido del chunk: {contenido}...")
        print(f"Caracteres del chunk: {len(texto)}")
        print(f"Dimensiones del embedding: {len(vector)}")
        print(f"Primeros 10 valores: {[round(float(valor), 4) for valor in vector[:10]]}")


if __name__ == "__main__":
    indexar()
