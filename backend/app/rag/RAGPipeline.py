import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import chromadb
import mlflow
import pandas as pd

from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity

try:
    from app.rag.RAGConfig import RAGConfig  # Using absolute import
except ImportError:
    from backend.app.rag.RAGConfig import RAGConfig


class RAGPipeline:
    """Base RAG Pipeline"""

    def __init__(self, config: RAGConfig):
        # print(f"Initializing RAGPipeline with config: {config}")
        self.config = config
        self.chroma_client = chromadb.HttpClient(host=config.host, port=config.port)
        self.collection = self.chroma_client.get_collection(config.collection_name)
        self.client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=config.llm_api_key)
        self.embedding_client = OpenAI(api_key=config.embedding_api_key)
        # print(f"RAGPipeline initialized with collection: {config.collection_name}")

    def get_embedding(self, text: str) -> List[float]:
        """Get embeddings using OpenAI API"""
        # print(f"Getting embedding for text: {text[:50]}...")
        response = self.embedding_client.embeddings.create(
            input=text, model=self.config.embedding_model
        )
        # print(f"Embedding generated with model: {self.config.embedding_model}")
        return response.data[0].embedding

    def semantic_search(self, query: str, k: Optional[int] = None) -> List[str]:
        """Search most relevant documents using ChromaDB"""
        # print(f"Performing semantic search for query: {query}")
        if k is None:
            k = self.config.top_k
        # print(f"Using k={k} for retrieval")

        query_embedding = self.get_embedding(query)
        results = self.collection.query(query_embeddings=[query_embedding], n_results=k)
        print(f"Found {len(results['documents'][0])} documents")
        return ' '.join(results["documents"][0])

    def generate_response(self, query: str, context: str, history="") -> str:
        """Generate response using OpenAI ChatGPT"""
        # print(f"Generating response for query: {query}")
        # print(f"Context length: {len(context)} characters")
        # print(f"History length: {len(history)} characters")
        
        prompt = f"""
            You are a helpful assistant. Answer the user using the context below and your understanding of the conversation.
            
            Retrieved Context:
            {context}
            
            Conversation History:
            {history}
            
            User: {query}
            Bot:
        """

        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
        )
        # print(f"Response generated with model: {self.config.llm_model}")
        return response.choices[0].message.content
    
    def should_refresh_context(self, user_input, history, previous_context) -> bool:
        # print(f"Evaluating if context refresh is needed for: {user_input}")
        prompt = f"""
            You are a reasoning assistant. Given the conversation so far and the user's new query,
            decide whether you need to retrieve new external context to answer, or if previous context is sufficient.

            Conversation History:
            {history}

            Previous Retrieved Context:
            {previous_context}

            User's New Query:
            {user_input}

            Should new information be retrieved from the knowledge base to answer this query?
            Respond only with "true" or "false".
            """

        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0  # deterministic
        )

        result = response.choices[0].message.content.strip().lower()
        # print(f"Context refresh decision: {result}")
        return result == "true"

    def query(self, query: str, relevant_docs=None, history="") -> Dict[str, Any]:
        """Complete RAG pipeline with metadata for evaluation"""
        # print(f"Processing query: {query}")
        # print(f"Existing relevant docs provided: {relevant_docs is not None}")
        
        # Retrieve relevant documents
        if relevant_docs is None:
            # print("No relevant docs provided, performing semantic search")
            relevant_docs = self.semantic_search(query)
        else:
            # If relevant_docs are provided, check if they are still relevant
            # print("Checking if existing context is still relevant")
            if self.should_refresh_context(query, history, relevant_docs):
                # If not relevant, perform a new semantic search
                # print("Context refresh needed, performing semantic search")
                relevant_docs = self.semantic_search(query)
            # else:
                # print("Using existing relevant docs")

        # Generate response
        # print("Generating response with retrieved documents")
        response = self.generate_response(query, relevant_docs, history)
        # print("Response generation complete")

        return {
            "query": query,
            "retrieved_documents": relevant_docs,
            "response": response,
        }