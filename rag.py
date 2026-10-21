from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from config import CHROMA_DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL, TEMPERATURE
from prompts import CONSULTA_PROMPT, RAG_PROMPT


def inicializar_rag(api_key, modelo_consulta, modelo_respuesta, k, temperatura=TEMPERATURE):
    """Configura los recursos de un visitante, sin modificar variables de entorno."""
    if not (CHROMA_DB_PATH / "chroma.sqlite3").is_file():
        raise FileNotFoundError("Falta la base de datos. Consulta la preparación en README.md.")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL, google_api_key=api_key,
        task_type="RETRIEVAL_QUERY")
    base_datos = Chroma(
        collection_name=COLLECTION_NAME, embedding_function=embeddings,
        persist_directory=str(CHROMA_DB_PATH),
        create_collection_if_not_exists=False)
    retriever = base_datos.as_retriever(search_kwargs={"k": k})
    llm_consulta = ChatGoogleGenerativeAI(
        model=modelo_consulta, google_api_key=api_key, temperature=0)
    llm_respuesta = ChatGoogleGenerativeAI(
        model=modelo_respuesta, google_api_key=api_key, temperature=temperatura)
    return (retriever, CONSULTA_PROMPT | llm_consulta | StrOutputParser(),
            RAG_PROMPT | llm_respuesta | StrOutputParser())


def responder(pregunta, historial, retriever, cadena_consulta, cadena_respuesta):
    """Devuelve el flujo de respuesta, la consulta y los documentos recuperados."""
    consulta = pregunta
    if historial:
        consulta = cadena_consulta.invoke({
            "pregunta": pregunta, "historial": historial}).strip() or pregunta
    documentos = retriever.invoke(consulta)
    if not documentos:
        return iter(["No se han recuperado fragmentos para responder."]), consulta, []
    fragmentos = []
    for numero, documento in enumerate(documentos, 1):
        pagina = documento.metadata.get("page", "No especificada")
        if isinstance(pagina, int):
            pagina += 1
        fuente = documento.metadata.get("source", "No especificada")
        fragmentos.append(
            f"[Fragmento {numero}] - Fuente: {fuente} - Página: {pagina}\n"
            f"{documento.page_content}")
    # El iterador entrega texto a medida que Gemini lo genera.
    respuesta = cadena_respuesta.stream({
        "pregunta": pregunta, "historial": historial,
        "contexto": "\n\n".join(fragmentos)})
    return respuesta, consulta, documentos
