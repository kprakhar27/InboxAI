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
        return results["documents"][0]

    def generate_response(self, query: str, context: List[str]) -> str:
        """Generate response using OpenAI ChatGPT"""
        prompt = f"""
            Based on the following context, please answer the question.
            Context: {' '.join(context)}
            Question: {query}
            Answer:
        """

        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
        )
        return response.choices[0].message.content

    def query(self, query: str) -> Dict[str, Any]:
        """Complete RAG pipeline with metadata for evaluation"""
        # Retrieve relevant documents
        relevant_docs = self.semantic_search(query)

        # Generate response
        response = self.generate_response(query, relevant_docs)

        return {
            "query": query,
            "retrieved_documents": relevant_docs,
            "response": response,
        }
