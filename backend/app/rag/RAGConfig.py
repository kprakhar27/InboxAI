from dataclasses import dataclass

@dataclass
class RAGConfig:
    """Configuration for a RAG pipeline"""
    embedding_model: str
    llm_model: str
    top_k: int
    temperature: float
    collection_name: str
    host: str
    port: str
    llm_api_key: str