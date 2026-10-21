import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from config import MODELOS, SEARCH_K, TEMPERATURE
from rag import inicializar_rag, responder

st.set_page_config(page_title="Asistente de ciberseguridad", page_icon="🛡️", layout="wide")
st.title("Asistente de ciberseguridad")
st.caption("Proyecto docente independiente basado en documentos públicos de INCIBE. No es una aplicación oficial de INCIBE.")

# Cada turno reúne la conversación y los documentos de ESA respuesta.
if "turnos" not in st.session_state:
    st.session_state.turnos = []

with st.sidebar:
    st.header("Configuración")
    api_key = st.text_input("API key de Google", type="password", key="api_key")
    st.caption("Se utiliza durante tu sesión para las llamadas a Google.")
    modelo_consulta = st.selectbox(
        "Modelo de reformulación", MODELOS, accept_new_options=True,
        help="Selecciona un modelo o escribe otro identificador de Gemini.")
    modelo_respuesta = st.selectbox(
        "Modelo de respuesta", MODELOS, accept_new_options=True,
        help="Selecciona un modelo o escribe otro identificador de Gemini.")
    k = st.number_input("Número de fragmentos (K)", min_value=1, value=SEARCH_K, step=1)
    temperatura = st.number_input(
        "Temperatura", min_value=0.0, max_value=2.0,
        value=TEMPERATURE, step=0.1, format="%.1f",
        help="Se aplica al modelo de respuesta en las siguientes preguntas.")
    if st.button("Vaciar conversación", use_container_width=True):
        st.session_state.turnos = []
        st.rerun()

# La barra lateral deja el espacio restante al chat y al panel de recuperación.
central, derecha = st.columns([3, 1.6])
with central:
    st.subheader("Conversación")
    conversacion = st.container(height=560)
    with conversacion:
        for turno in st.session_state.turnos:
            with st.chat_message("user"):
                st.text(turno["pregunta"])
            with st.chat_message("assistant"):
                st.markdown(turno["respuesta"])
    pregunta = st.chat_input("Escribe tu pregunta…", disabled=not api_key.strip())
    if not api_key.strip():
        st.info("Introduce tu API key de Google para comenzar.")

with derecha:
    st.subheader("Consultas y fragmentos")
    with st.container(height=640):
        for numero, turno in enumerate(st.session_state.turnos, 1):
            st.markdown(f"**Pregunta {numero}**")
            st.text(turno["consulta"])
            for indice, documento in enumerate(turno["documentos"], 1):
                pagina = documento.metadata.get("page", "No especificada")
                if isinstance(pagina, int):
                    pagina += 1
                with st.expander(f"Fragmento {indice} · Página {pagina}"):
                    st.text(f"Fuente: {documento.metadata.get('source', 'No especificada')}")
                    # Texto completo: el mismo fragmento enviado al modelo.
                    st.text(documento.page_content)
            st.divider()

if pregunta:
    # Reconstruimos el historial solo con los turnos completados de esta sesión.
    historial = []
    for turno in st.session_state.turnos:
        historial.extend([HumanMessage(content=turno["pregunta"]),
                          AIMessage(content=turno["respuesta"])])
    with conversacion:
        with st.chat_message("user"):
            st.text(pregunta)
        try:
            with st.spinner("Consultando los documentos…"):
                recursos = inicializar_rag(
                    api_key.strip(), modelo_consulta, modelo_respuesta, int(k), float(temperatura))
                flujo, consulta, documentos = responder(pregunta, historial, *recursos)
            with st.chat_message("assistant"):
                # Muestra los bloques recibidos y devuelve el texto completo.
                respuesta = st.write_stream(flujo)
        except FileNotFoundError:
            st.error("Falta chroma_db. Sigue la preparación indicada en README.md.")
        except Exception:
            # No mostramos excepciones del proveedor: podrían contener datos sensibles.
            st.error("No se ha podido completar la consulta. Comprueba la clave, los modelos, "
                     "la cuota disponible, la conexión y la base de datos.")
        else:
            st.session_state.turnos.append({
                "pregunta": pregunta, "respuesta": respuesta,
                "consulta": consulta, "documentos": documentos})
            st.rerun()
