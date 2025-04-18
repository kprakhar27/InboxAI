from typing import Any, Dict, List, Optional

import chromadb
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from openai import OpenAI
from RAGConfig import RAGConfig
from langchain_core.pydantic_v1 import BaseModel, Field
from typing_extensions import TypedDict

class HybridGraphState(TypedDict):
    """
    Represents the state of our hybrid RAG graph.
    Attributes:
        question: user's question
        generation: LLM generation
        documents: list of documents
        keyword_docs: documents retrieved via keyword search
        vector_docs: documents retrieved via vector search
        reranked_docs: documents after reranking
    """

    question: str
    generation: str
    documents: List[str]
    keyword_docs: List[str]
    vector_docs: List[str]
    reranked_docs: List[str]

class HybridRAGPipeline:
    """Hybrid RAG Pipeline with MLflow integration"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.chroma_client = chromadb.HttpClient(
            host=config.host, port=config.port
        )
        self.collection = self.chroma_client.get_collection(config.collection_name)
        self.client = OpenAI()

        # Setup RAG chain
        self.rag_llm = ChatOpenAI(
            api_key=config.llm_api_key,
            model_name=config.llm_model,
            temperature=config.temperature,
        )
        self.rag_prompt = ChatPromptTemplate.from_template(
            """
            Based on the following context, please answer the question.
            Context: {context}
            Question: {question}
            Answer:
            """
        )
        self.rag_chain = self.rag_prompt | self.rag_llm | StrOutputParser()

        # Setup keyword extractor
        self.keyword_prompt = ChatPromptTemplate.from_template(
            """Extract the 3-5 most important keywords from this question for search purposes.
            Return only the keywords separated by commas without any additional text.
            
            Question: {question}
            """
        )
        self.keyword_extractor = self.keyword_prompt | self.rag_llm | StrOutputParser()

        # Setup reranker
        self.reranker_prompt = ChatPromptTemplate.from_template(
            """You are a document reranker. Your task is to rank the documents based on their relevance 
            to the question. Return the indices of the documents in order of relevance, separated by commas.
            
            Question: {question}
            
            Documents:
            {documents}
            
            Document indices in order of relevance (most relevant first):
            """
        )
        self.reranker = self.reranker_prompt | self.rag_llm | StrOutputParser()

        # Define state model for graph
        class HybridGraphState(BaseModel):
            question: str
            documents: Optional[List[str]] = None
            generation: Optional[str] = None
            keyword_docs: Optional[List[str]] = None
            vector_docs: Optional[List[str]] = None
            reranked_docs: Optional[List[str]] = None

        # Define graph
        self.workflow = StateGraph(HybridGraphState)
        self.workflow.add_node("keyword_search", self.keyword_search)
        self.workflow.add_node("vector_search", self.vector_search)
        self.workflow.add_node("combine_results", self.combine_results)
        self.workflow.add_node("rerank", self.rerank_documents)
        self.workflow.add_node("generate", self.generate)

        # Build graph
        self.workflow.add_edge(START, "keyword_search")
        self.workflow.add_edge(START, "vector_search")
        self.workflow.add_edge("keyword_search", "combine_results")
        self.workflow.add_edge("vector_search", "combine_results")
        self.workflow.add_edge("combine_results", "rerank")
        self.workflow.add_edge("rerank", "generate")
        self.workflow.add_edge("generate", END)

        # Compile
        self.app = self.workflow.compile()

    def get_embedding(self, text: str) -> List[float]:
        """Get embeddings using OpenAI API"""
        response = self.client.embeddings.create(
            input=text, model=self.config.embedding_model
        )
        return response.data[0].embedding

    def semantic_search(self, query: str, k: Optional[int] = None) -> List[str]:
        """Search most relevant documents using ChromaDB (vector search)"""
        if k is None:
            k = self.config.top_k

        query_embedding = self.get_embedding(query)
        results = self.collection.query(query_embeddings=[query_embedding], n_results=k)
        return results["documents"][0]

    def keyword_search(self, state):
        """Perform keyword-based search"""
        question = state.question
        keywords = self.keyword_extractor.invoke({"question": question})

        # Query Chroma using the keywords
        results = self.collection.query(
            query_texts=[keywords], n_results=self.config.top_k
        )

        keyword_docs = results.get("documents", [[]])[0]
        return {"question": question, "keyword_docs": keyword_docs}

    def vector_search(self, state):
        """Perform vector-based search"""
        question = state.question

        # Get embeddings and search using semantic search
        vector_docs = self.semantic_search(question)

        return {"question": question, "vector_docs": vector_docs}

    def combine_results(self, state):
        """Combine results from keyword and vector search"""
        question = state.question
        keyword_docs = state.keyword_docs if hasattr(state, "keyword_docs") else []
        vector_docs = state.vector_docs if hasattr(state, "vector_docs") else []

        # Combine and deduplicate
        all_docs = []
        for doc in keyword_docs + vector_docs:
            if doc not in all_docs:
                all_docs.append(doc)

        return {
            "question": question,
            "keyword_docs": keyword_docs,
            "vector_docs": vector_docs,
            "documents": all_docs,
        }

    def rerank_documents(self, state):
        """Rerank documents using an LLM"""
        question = state.question
        documents = state.documents

        if not documents:
            return {**state.__dict__, "reranked_docs": []}

        # Format documents for the reranker
        formatted_docs = "\n\n".join([f"{i}: {doc}" for i, doc in enumerate(documents)])

        # Get reranking indices
        try:
            reranking_result = self.reranker.invoke(
                {"question": question, "documents": formatted_docs}
            )

            # Parse the indices
            indices = [int(idx.strip()) for idx in reranking_result.split(",")]

            # Rerank the documents
            reranked_docs = [documents[idx] for idx in indices if idx < len(documents)]

            # If parsing fails, use the original order
            if not reranked_docs:
                reranked_docs = documents
        except:
            reranked_docs = documents

        return {**state.__dict__, "reranked_docs": reranked_docs}

    def generate(self, state):
        """Generate an answer based on reranked documents"""
        question = state.question
        documents = state.reranked_docs if hasattr(state, "reranked_docs") else []

        if not documents:
            generation = "I don't have enough information to answer this question."
        else:
            # Use top documents (limit to ensure context fits)
            context = "\n\n".join(documents[:3])
            generation = self.rag_chain.invoke(
                {"context": context, "question": question}
            )

        return {
            **state.__dict__,
            "question": question,
            "documents": documents,
            "generation": generation,
        }

    def retrieve(self, state):
        """Compatibility method with CRAG - runs the hybrid retrieval process"""
        # This just initializes the workflow execution
        return state

    def evaluate_documents(self, state):
        """Compatibility method with CRAG - documents are already evaluated in the reranking step"""
        return state

    def transform_query(self, state):
        """Compatibility method with CRAG"""
        return state

    def decide_to_generate(self, state):
        """Compatibility method with CRAG"""
        return "generate"

    def generate_response(self, query: str, context: List[str]) -> str:
        """Generate response using the RAG chain (for compatibility with original RAGPipeline)"""
        return self.rag_chain.invoke(
            {"context": "\n\n".join(context), "question": query}
        )

    def query(self, query: str) -> Dict[str, Any]:
        """Complete RAG pipeline with metadata for evaluation (compatible with original RAGPipeline interface)"""
        # Run the graph
        initial_state = {
            "question": query,
            "generation": "",
            "documents": [],
            "keyword_docs": [],
            "vector_docs": [],
            "reranked_docs": [],
        }

        output = self.app.invoke(initial_state)

        return {
            "query": query,
            "retrieved_documents": output.get("documents", []),
            "response": output.get("generation", ""),
        }
