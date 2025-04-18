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

class GraphState(TypedDict):
    """
    Represents the state of our graph.
    Attributes:
        question: question
        generation: LLM generation
        documents: list of documents
    """

    question: str
    generation: str
    documents: List[str]


class RetrievalEvaluator(BaseModel):
    """Classify retrieved documents based on how relevant it is to the user's question."""

    binary_score: str = Field(
        description="Emails are relevant to the question, 'yes' or 'no'"
    )

class CRAGPipeline:
    """Conditional RAG Pipeline with MLflow integration"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.chroma_client = chromadb.HttpClient(host=config.host, port=config.port)
        self.collection = self.chroma_client.get_collection(config.collection_name)
        self.client = OpenAI(api_key=config.llm_api_key)

        # Setup RAG chain
        self.rag_llm = ChatOpenAI(
            api_key=config.llm_api_key,
            model_name=config.llm_model,
            temperature=config.temperature,
        )
        self.rag_prompt = ChatPromptTemplate.from_template(
            """
            You are a helpful assistant. Answer the user using the context below and your understanding of the conversation.
            
            Retrieved Context:
            {context}
            
            Conversation History:
            {history}
            
            User: {query}
            Bot:
        """
        )
        self.rag_chain = self.rag_prompt | self.rag_llm | StrOutputParser()

        # Setup retrieval evaluator
        self.retrieval_evaluator_llm = ChatOpenAI(
            api_key=config.llm_api_key, model=config.llm_model, temperature=0
        )
        self.structured_llm_evaluator = (
            self.retrieval_evaluator_llm.with_structured_output(RetrievalEvaluator)
        )
        self.system = """You are a document retrieval evaluator that's responsible for checking the relevancy of retrieved documents to the user's question. 
            If the document contains keyword(s) or semantic meaning or any specific related info that might contain then grade it as relevant.
            Output a binary score 'yes' or 'no' to indicate whether the document is relevant to the question."""
        self.retrieval_evaluator_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system),
                (
                    "human",
                    "Retrieved document: \n\n {document} \n\n User question: {question}",
                ),
            ]
        )
        self.retrieval_grader = (
            self.retrieval_evaluator_prompt | self.structured_llm_evaluator
        )

        # Setup question rewriter
        self.question_rewriter_llm = ChatOpenAI(
            api_key=config.llm_api_key, model=config.llm_model, temperature=0
        )
        self.system_rewrite = """You are a question re-writer that converts an input question to a better version that is optimized 
             for search. Look at the input and try to reason about the underlying semantic intent / meaning."""
        self.re_write_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_rewrite),
                (
                    "human",
                    "Here is the initial question: \n\n {question} \n Formulate an improved question.",
                ),
            ]
        )
        self.question_rewriter = (
            self.re_write_prompt | self.question_rewriter_llm | StrOutputParser()
        )

        # Define graph nodes
        self.workflow = StateGraph(GraphState)
        self.workflow.add_node("retrieve", self.retrieve)
        self.workflow.add_node("grade_documents", self.evaluate_documents)
        self.workflow.add_node("generate", self.generate)
        self.workflow.add_node("transform_query", self.transform_query)

        # Build graph
        self.workflow.add_edge(START, "retrieve")
        self.workflow.add_edge("retrieve", "grade_documents")
        self.workflow.add_conditional_edges(
            "grade_documents",
            self.decide_to_generate,
            {
                "transform_query": "transform_query",
                "generate": "generate",
            },
        )
        self.workflow.add_edge("transform_query", "retrieve")
        self.workflow.add_edge("generate", END)

        # Compile
        self.app = self.workflow.compile()

    def get_embedding(self, text: str) -> List[float]:
        """Get embeddings using OpenAI API"""
        response = self.client.embeddings.create(
            input=text, model=self.config.embedding_model
        )
        return response.data[0].embedding

    def semantic_search(self, query: str, k: Optional[int] = None) -> str:
        """Search most relevant documents using ChromaDB"""
        if k is None:
            k = self.config.top_k

        query_embedding = self.get_embedding(query)
        results = self.collection.query(query_embeddings=[query_embedding], n_results=k)
        return ' '.join(results["documents"][0])

    def retrieve(self, state):
        """
        Retrieve documents
        Args:
            state (dict): The current graph state
        Returns:
            state (dict): New key added to state, documents, that contains retrieved documents
        """
        question = state["question"]
        documents = self.semantic_search(question)
        return {"documents": documents, "question": question}

    def evaluate_documents(self, state):
        """
        Determines whether the retrieved documents are relevant to the question.
        Args:
            state (dict): The current graph state
        Returns:
            state (dict): Updates documents key with only filtered relevant documents
        """
        question = state["question"]
        documents = state["documents"]
        filtered_docs = []
        for d in documents:
            score = self.retrieval_grader.invoke({"question": question, "document": d})
            grade = score.binary_score
            if grade == "yes":
                filtered_docs.append(d)
        return {"documents": filtered_docs, "question": question}

    def generate(self, state):
        """
        Generate answer
        Args:
            state (dict): The current graph state
        Returns:
            state (dict): New key added to state, generation, that contains LLM generation
        """
        question = state["question"]
        documents = state["documents"]
        generation = self.rag_chain.invoke(
            {"context": " ".join(documents), "question": question}
        )
        return {"documents": documents, "question": question, "generation": generation}

    def transform_query(self, state):
        """
        Transform the query to produce a better question.
        Args:
            state (dict): The current graph state
        Returns:
            state (dict): Updates question key with a re-phrased question
        """
        question = state["question"]
        documents = state["documents"]
        better_question = self.question_rewriter.invoke({"question": question})
        return {"documents": documents, "question": better_question}

    def decide_to_generate(self, state):
        """
        Determines whether to generate an answer, or re-generate a question.
        Args:
            state (dict): The current graph state
        Returns:
            str: Binary decision for next node to call
        """
        documents = state["documents"]
        if len(documents) > 0:
            return "generate"
        else:
            return "transform_query"

    def generate_response(self, query: str, context: List[str]) -> str:
        """Generate response using OpenAI ChatGPT (for compatibility with original RAGPipeline)"""
        return self.rag_chain.invoke({"context": " ".join(context), "question": query})

    def query(self, query: str) -> Dict[str, Any]:
        """Complete RAG pipeline with metadata for evaluation (compatible with original RAGPipeline interface)"""
        # Run the graph
        output = self.app.invoke({"question": query})

        return {
            "query": query,
            "retrieved_documents": output.get("documents", []),
            "response": output.get("generation", ""),
        }
