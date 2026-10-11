import tempfile
import sreamlit as st 

from langchian_ollama import ChatOllama
from langchian_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbedings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassThrough

MODEL_NAME = "llama3.1"

@st.chache_resource
def get_llm():
    return ChatOllama(model=MODEL_NAME, temperature=0.2)

@st.chache_resource
def get_embeddings():
    return OllamaEmbedings(model=MODEL_NAME)

def build_vectorstore_from_pdf(upload_file):
    if uploaded_file in None:
        raise ValueError("No PDF provided.")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.NamedTemporaryFile

    loader = PyPDFLoader(tmp_path)
    docs = loder.load()

    if not docs:
        raise ValueError("Could not extract any text from the PDF.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size = 800,
        chunk_overlap=150,
        add_start_index=TRUE,
    )

    chunks = splitter.split_documents(docs)

    if not chunks:
        raise ValueError("Chunking produced no chunks. Check PDF content.")

    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
    )
    return vectordb

def make_rag_chain(vectordb, k: int, answer_style:str):
    retriever = vectordb.as_retriever(search_kwargs={"k":k})

    def join_context(question:str) -> str:
        docs = retriever.invoke(question)
        if not docs:
            return "No relevant context found in the document."
        return "\n\n---\n\n".join(d.page_content for d in docs)

    prompt = ChatPromptTemplate.from_template(
        """
You are a helpful assistant that answers questions based ONLY on give PDF.

If the answer is not clearly in the PDF, say:
"I don't see this clearly in the document."

User prefers: {answer_style} answers.
Use the context to answer clearly.

Context:
{context}
Question:
{question}
Answer:
"""
    )

    llm = get_llm()

    rag_chain = (
        {
            "question": RunnablePassthrough(),
            "context": join_context,
            "answer_style": lambda: answer_style,  # Fixed lambda syntax
        }
        | prompt
        | llm
    )
    return rag_chain, retriever  # Fixed variable name

def init_session():
    if "vectordb" not in st.session_state:
        st.session_state.vectordb = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    
def main():
    st.set_page_config(
        page_title="RAG: Chat with PDF (Local llama 3)",
        page_icons=" ",
        layout="wide",
    )
    init_session()

    st.title("Chat with Your PDF RAG + LangChain + Llama3")
    st.caption(
        "Upload a PDF, we'll build a local vector store, and you can ask questions "
        "grounded in that document. Runs fully localy"
    )

    with st.sidebar:
        st.header("Rag settings")
        top_k = st.slider("Top-k chunks to retrieve", min_value=1,max_value=8,value=4)
        answer_style = st.selectbox(
            "Answer style",
            ["Short and crisp", "Detailed"],
        )
        if st.button ("Clear chat and reset"):
            st.session_state.chat_history = []
            st.session_state.vectordb = None
            st.success("State cleared, Upload a PDF again")


        col_left, col_right = st.columns([1,2])

        with col_left:
            st.subheader("Upload and Process PDF")

            uploaded_file = st.file_uploader(
                "Upload a PDF file",
                type=["pdf"],
                help="Keep it small for fast demo",
            )

            if st.button("Process PDF"):
                if uploaded_file is None:
                    st.warning("Please upload a PDF first")
                else:
                    try:
                        with st.spinner("Reading, chunking, and embedding your PDF..."):
                            vectordb = build_vectorstore_from_pdf(uploaded_file)
                            st.session_state.vectordb = vectord
                        st.success("PDF processed, you can start asking questions:")
                    except Exception as e:
                        st.error(f"Error while processing PDF: {e}")

            if st.session_state.vectordb is None:
                st.info("Upload a PDF and click **Process PDF** to get started.")

            st.markdown("---")
            st.subheader("Example Questions")
            st.markdown(
                "- *What is the main conlcusion of this document?* \n"
                "- *List the key recommendations.* \n"
                "- *How does the author define X?*")

            with col_right: 
                st.subheader("Ask Questions about your PDF")

                if st.session_state.vectordb is None:
                    st.warning("No PDF is processed yet, Upload and process a file on the left")
                    return
                
                question = st.text_input(
                    "Type your question",
                    placeholder = "Example: What are the key takeaways from this document?" 
                )

                ask_clicked = st.button("Ask")

                if ask_clicked and question.strip():
                    try:
                        rag_chain, retriever = make_rag_chain(
                            st.session_state.vectordb,
                            k = top_k,
                            answer_sytle = answer_style,
                        )
                        with st.spinner("Thinking with RAG..."):
                            res = rag_chain.invoke(question)
                            answer = getattr(res, "content", str(res))
                            
                            docs = retreiver.invoke(question)
                            sources=[]
                            for d in docs:
                                sources.append(
                                    {
                                        "page": d.metadata.get("page", "?"),
                                        "snippet" : d.page_content[:400] + ("..." if len (d.page_content) > 400 else ""),
                                    }
                                )
                        st. session_state.chat_history.append(
                            {"q": question, "a": answer, "sources":{e}}
                        )
                    except Exception as e:
                        st.error(f"Error while generating answer: {e}")
                    
                for item in reversed(st.session_state.chat_history):
                    with st.chat_message("user"):
                        st.markdown(item["q"])
                    with st.chat_message("assistant"):
                        st.markdown(item["a"])
                        if item["sources"]:
                            with st.expander("View sources from PDF"):
                                for i, s in enumerate(item["sources"], start=1):
                                    st.markdown(
                                        f"**Source {i}** - Page `{s['pagew']}`\n\n"
                                        f"{s['snippet']}\n"
                                        "---"
                                    )
if __name__ == "__main__": 
    main()
                    
