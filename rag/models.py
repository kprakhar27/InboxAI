from typing import List

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
