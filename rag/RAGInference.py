# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from RAGConfig import RAGConfig
from CRAGPipeline import CRAGPipeline
from HybridRAGPipeline import HybridRAGPipeline
from RAGPipeline import RAGPipeline
import os
from dotenv import load_dotenv
load_dotenv('/Users/rounakbende/Documents/Git/InboxAI/data_pipeline/.env')
app = FastAPI(title="RAG Pipeline API")

# Request   models
class QueryRequest(BaseModel):
    question: str
    pipeline_type: str = "crag"
    #embedding_model: Optional[str] = None
    llm_model: Optional[str] = "gpt-4o-mini"
    top_k: int = 3
    temperature: Optional[float] = None
    collection_name: str = None


class GenerateRequest(BaseModel):
    question: str
    context: List[str]
    pipeline_type: str = "crag"
    #embedding_model: Optional[str] = None
    llm_model: Optional[str] = "gpt-4o-mini"
    top_k: int = 3
    temperature: Optional[float] = None
    collection_name: str = None


class RerankRequest(BaseModel):
    question: str
    documents: List[str]
    #embedding_model: Optional[str] = None
    llm_model: Optional[str] = "gpt-4o-mini"
    top_k: Optional[int] = 3
    temperature: Optional[float] = None
    collection_name: str= None


# Common endpoints
@app.post("/query")
async def query_pipeline(request: QueryRequest):
    """Execute full RAG pipeline"""
    try:
        config = RAGConfig(
            embedding_model="text-embedding-3-small",
            llm_model=request.llm_model or "gpt-4o-mini",
            top_k=request.top_k or 3,
            temperature=request.temperature or 0.0,
            collection_name=request.collection_name,
            host=os.getenv('DB_HOST'),
            port=os.getenv('CHROMA_PORT'),
            llm_api_key=os.getenv('OPEN_API_KEY')
        )
        pipeline = {
            "crag": CRAGPipeline(config),
            "rag": RAGPipeline(config),
            "hybrid": HybridRAGPipeline(config)
        }[request.pipeline_type]
        return pipeline.query(request.question)
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid pipeline type")

@app.post("/retrieve")
async def retrieve_documents(request: QueryRequest):
    """Retrieve documents using semantic search"""
    try:
        config = RAGConfig(
            embedding_model="text-embedding-3-small",
            llm_model=request.llm_model or "gpt-4o-mini",
            top_k=request.top_k or 3,
            temperature=request.temperature or 0.0,
            collection_name=request.collection_name,
            host=os.getenv('DB_HOST'),
            port=os.getenv('CHROMA_PORT'),
            llm_api_key=os.getenv('OPEN_API_KEY')
        )
        pipeline = {
            "crag": CRAGPipeline(config),
            "rag": RAGPipeline(config),
            "hybrid": HybridRAGPipeline(config)
        }[request.pipeline_type]
        return {
            "documents": pipeline.semantic_search(request.question),
            "pipeline": request.pipeline_type
        }
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid pipeline type")

@app.post("/generate")
async def generate_answer(request: GenerateRequest):
    """Generate answer with custom context"""
    try:
        config = RAGConfig(
            embedding_model="text-embedding-3-small",
            llm_model=request.llm_model or "gpt-4o-mini",
            top_k=request.top_k or 3,
            temperature=request.temperature or 0.0,
            collection_name=request.collection_name,
            host=os.getenv('DB_HOST'),
            port=os.getenv('CHROMA_PORT'),
            llm_api_key=os.getenv('OPEN_API_KEY')
        )
        pipeline = {
            "crag": CRAGPipeline(config),
            "rag": RAGPipeline(config),
            "hybrid": HybridRAGPipeline(config)
        }[request.pipeline_type]
        return {
            "response": pipeline.generate_response(request.question, request.context),
            "pipeline": request.pipeline_type
        }
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid pipeline type")

# Hybrid-specific endpoints
@app.post("/hybrid/keyword-search")
async def keyword_search(request: QueryRequest):
    """Perform keyword-based search (HybridRAG only)"""
    if request.pipeline_type != "hybrid":
        raise HTTPException(status_code=400, detail="Keyword search only available for Hybrid pipeline")
    config = RAGConfig(
            embedding_model="text-embedding-3-small",
            llm_model=request.llm_model or "gpt-4o-mini",
            top_k=request.top_k or 3,
            temperature=request.temperature or 0.0,
            collection_name=request.collection_name,
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('CHROMA_PORT')),
            llm_api_key=os.getenv('OPEN_API_KEY')
        )
    pipeline = {
        "crag": CRAGPipeline(config),
        "rag": RAGPipeline(config),
        "hybrid": HybridRAGPipeline(config)
    }[request.pipeline_type]
    state = pipeline.keyword_search({"question": request.question})
    return {
        "keyword_documents": state["keyword_docs"],
        "question": request.question
    }

@app.post("/hybrid/rerank")
async def rerank_documents(request: RerankRequest):
    """Rerank documents (HybridRAG only)"""
    config = RAGConfig(
            embedding_model=request.embedding_model or "text-embedding-3-small",
            llm_model=request.llm_model or "gpt-4o-mini",
            top_k=request.top_k or 3,
            temperature=request.temperature or 0.0,
            collection_name=request.collection_name,
            host=os.getenv('CHROMA_HOST'),
            port=int(os.getenv('CHROMA_PORT')),
            llm_api_key=os.getenv('OPEN_API_KEY')
        )
    pipeline = {
        "crag": CRAGPipeline(config),
        "rag": RAGPipeline(config),
        "hybrid": HybridRAGPipeline(config)
    }[request.pipeline_type]
    state = {
        "question": request.question,
        "documents": request.documents,
        "reranked_docs": []
    }
    new_state = pipeline.rerank_documents(state)
    return {
        "reranked_documents": new_state["reranked_docs"],
        "original_documents": request.documents
    }

@app.get("/pipelines")
async def list_available_pipelines():
    """List available pipeline types"""
    return {
        "available_pipelines": ["crag", "rag", "hybrid"],
        "description": {
            "crag": "Conditional RAG with query transformation and document grading",
            "hybrid": "Hybrid RAG with keyword/vector search and reranking"
        }
    }
