import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import chromadb
import mlflow
import pandas as pd
from openai import OpenAI
from RAGConfig import RAGConfig
from sklearn.metrics.pairwise import cosine_similarity


class RAGPipeline:
    """Base RAG Pipeline"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.chroma_client = chromadb.HttpClient(host=config.host, port=config.port)
        self.collection = self.chroma_client.get_collection(config.collection_name)
        self.client = OpenAI(api_key=config.llm_api_key)

    def get_embedding(self, text: str) -> List[float]:
        """Get embeddings using OpenAI API"""
        response = self.client.embeddings.create(
            input=text, model=self.config.embedding_model
        )
        return response.data[0].embedding

    def semantic_search(self, query: str, k: Optional[int] = None) -> List[str]:
        """Search most relevant documents using ChromaDB"""
        if k is None:
            k = self.config.top_k

        query_embedding = self.get_embedding(query)
        results = self.collection.query(query_embeddings=[query_embedding], n_results=k)
        return ' '.join(results["documents"][0])

    def generate_response(self, query: str, context: str, history="") -> str:
        """Generate response using OpenAI ChatGPT"""
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
        return response.choices[0].message.content
    
    def should_refresh_context(self, user_input, history, previous_context) -> bool:
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

        result = response['choices'][0]['message']['content'].strip().lower()
        return result == "true"

    def query(self, query: str, relevant_docs=None, history="") -> Dict[str, Any]:
        """Complete RAG pipeline with metadata for evaluation"""
        # Retrieve relevant documents
        if relevant_docs is None:
            relevant_docs = self.semantic_search(query)
        else:
            # If relevant_docs are provided, check if they are still relevant
            if self.should_refresh_context(query, history, relevant_docs):
                # If not relevant, perform a new semantic search
                relevant_docs = self.semantic_search(query)

        # Generate response
        response = self.generate_response(query, relevant_docs, history)

        return {
            "query": query,
            "retrieved_documents": relevant_docs,
            "response": response,
        }
