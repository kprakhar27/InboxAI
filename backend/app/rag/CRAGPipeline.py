import json
import os
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import pandas as pd
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from openai import OpenAI
from typing_extensions import TypedDict

try:
    from app.rag.RAGConfig import RAGConfig
except ImportError:
    from backend.app.rag.RAGConfig import RAGConfig



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
        self.chroma_client = chromadb.HttpClient(
            host=config.host, port=config.port
        )
        self.collection = self.chroma_client.get_collection(config.collection_name)
        self.client = ChatGroq(model_name=config.llm_model)
        self.embedding_client = OpenAI(api_key=config.embedding_api_key)
        # Setup RAG chain
        self.rag_llm = ChatGroq(
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

        # Setup retrieval evaluator
        self.retrieval_evaluator_llm = ChatGroq(
            model=self.config.llm_model, temperature=0
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
        self.question_rewriter_llm = ChatGroq(
            model=self.config.llm_model
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
        self.workflow.add_edge("transform_query", "generate")
        self.workflow.add_edge("generate", END)

        # Compile
        self.app = self.workflow.compile()

    def get_embedding(self, text: str) -> List[float]:
        """Get embeddings using OpenAI API"""
        response = self.embedding_client.embeddings.create(
            input=text, model=self.config.embedding_model
        )
        return response.data[0].embedding

    def semantic_search(self, query: str, k: Optional[int] = None) -> List[str]:
        """Search most relevant documents using ChromaDB"""
        if k is None:
            k = self.config.top_k

        query_embedding = self.get_embedding(query)
        results = self.collection.query(query_embeddings=[query_embedding], n_results=k)
        return results["documents"][0]

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

    def generate_response(self, query: str, context: str, history="") -> str:
        """Generate response using Groq with improved prompt engineering"""
        print(f"Generating response for query: {query}")
        print(f"Context length: {len(context)} characters")
        print(f"History length: {len(history)} characters")
        
        prompt = f"""
            You are a helpful AI assistant. Your task is to provide accurate and relevant answers based on the given context and conversation history.
            
            Context Information:
            {context}
            
            Previous Conversation:
            {history}
            
            Current Query: {query}
            
            Instructions:
            1. Use the provided context to answer the query
            2. If the context doesn't contain relevant information, acknowledge this and provide a general response
            3. Maintain consistency with the conversation history
            4. Be concise and direct in your response
            
            Response:
        """

        response = self.client.invoke(prompt)
        print(f"Response generated with model: {self.config.llm_model}")
        return response.content
    
    def should_refresh_context(self, user_input: str, history: str, previous_context: str) -> bool:
        """Enhanced context refresh decision making"""
        print(f"Evaluating if context refresh is needed for: {user_input}")
        prompt = f"""
            As a context evaluation system, analyze if new information needs to be retrieved based on:
            
            1. Current Query: {user_input}
            
            2. Previous Context: {previous_context}
            
            3. Conversation History: {history}
            
            Determine if the current context is sufficient to answer the query accurately.
            Consider:
            - Topic shifts in the conversation
            - Specific details requested in the query
            - Relevance of existing context
            
            Respond with only "true" or "false".
            """

        response = self.client.invoke(prompt)
        result = response.content.strip().lower()
        print(f"Context refresh decision: {result}")
        return result == "true"

    def query(self, query: str, relevant_docs: Optional[str] = None, history: str = "") -> Dict[str, Any]:
        """Complete RAG pipeline with metadata for evaluation"""
        print(f"Processing query: {query}")
        print(f"Existing relevant docs provided: {relevant_docs is not None}")
        
        # If relevant_docs are provided, check if they are still relevant
        if relevant_docs is not None:
            print("Checking if existing context is still relevant")
            if self.should_refresh_context(query, history, relevant_docs):
                # If not relevant, perform a new semantic search
                print("Context refresh needed, performing semantic search")
                relevant_docs = self.semantic_search(query)
            else:
                print("Using existing relevant docs")
        
        # Run the workflow
        print("Invoking workflow")
        output = self.app.invoke({"question": query})
        
        # Generate response with enhanced context
        print("Generating response with retrieved documents")
        response = self.generate_response(query, output.get("documents", ""), history)
        print("Response generation complete")

        return {
            "query": query,
            "retrieved_documents": output.get("documents", ""),
            "response": response,
            "context_refreshed": relevant_docs is not None
        }