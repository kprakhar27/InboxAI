import importlib
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import chromadb
import mlflow
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from RAGBiasAnalyzer import RAGBiasAnalyzer
from RAGEvaluator import RAGEvaluator
from backend.app.rag.RAGConfig import RAGConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
from backend.app.models import db, RAG

# Initialize MLflow
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))

print(os.getenv("GROQ_API_KEY"))
def get_class_from_input(module_path: str, class_name: str):
    """
    Dynamically load a class from a given file path.
    
    Args:
        module_path: str – full path to the .py file
        class_name: str – class name defined in that module

    Returns:
        class object
    """
    # logger.debug(f"Attempting to load class '{class_name}' from {module_path}")
    module_name = os.path.splitext(os.path.basename(module_path))[0]  # e.g., RAGConfig
    # logger.debug(f"Module name: {module_name}")
    spec = importlib.util.spec_from_file_location(module_name, module_path)

    if spec is None or spec.loader is None:
        # logger.error(f"Error: Could not load spec for {module_path}")
        raise ImportError(f"Could not load spec for {module_path}")

    # logger.debug(f"Successfully loaded spec for {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    # logger.debug(f"Executing module {module_name}")
    spec.loader.exec_module(module)

    if not hasattr(module, class_name):
        # logger.error(f"Error: Class '{class_name}' not found in {module_path}")
        raise ImportError(f"Class '{class_name}' not found in {module_path}")

    # logger.debug(f"Successfully loaded class '{class_name}' from {module_path}")
    return getattr(module, class_name)

def check_llm_results(results, thresholds):
    """Check if LLM evaluation results exceed the given thresholds.

    Args:
        results (dict): LLM evaluation results.
        thresholds (dict): Threshold values for evaluation.

    Returns:
        dict: Boolean flags indicating if each category passes and overall result.
    """
    def check_overall(metrics, threshold_metrics):
        return all(metrics.get(key, 0) >= threshold_metrics.get(key, 0) for key in threshold_metrics)

    # Embedding Evaluation
    embedding_metrics = results.get("embedding_evaluation", {}).get("overall", {})
    embedding_pass = check_overall(embedding_metrics, thresholds.get("embedding_evaluation", {}))

    # Top-K Evaluation (skip if error)
    top_k_eval = results.get("top_k_evaluation", {})
    top_k_pass = False
    if "error" not in top_k_eval:
        top_k_pass = all(
            top_k_eval.get(k, {}).get("answer_accuracy", 0) >= thresholds["top_k_evaluation"].get(k, 0)
            for k in thresholds["top_k_evaluation"]
        )

    # RAG System Evaluation
    rag_metrics = results.get("rag_system_evaluation", {}).get("overall", {})
    rag_pass = check_overall(rag_metrics, thresholds.get("rag_system_evaluation", {}))

    return {
        "embedding_pass": embedding_pass,
        "top_k_pass": top_k_pass,
        "rag_pass": rag_pass,
        "overall_pass": embedding_pass and top_k_pass and rag_pass
    }


def main():
    print("Starting RAG Evaluator...")
    print(f"Arguments provided: {sys.argv}")

    # Get test dataset path from environment
    test_dataset_path = os.getenv("TEST_DATASET_PATH")
    if not test_dataset_path:
        print("Error: TEST_DATASET_PATH environment variable not set")
        sys.exit(1)
    print(f"Test dataset path: {test_dataset_path}")

    # Define RAG configuration
    config = RAGConfig(
        embedding_model=os.getenv("EMBEDDING_MODEL"),
        llm_model=os.getenv("LLM_MODEL"),
        top_k=int(os.getenv("TOP_K", "5")),
        temperature=float(os.getenv("TEMPERATURE", "0.7")),
        collection_name=os.getenv("CHROMA_COLLECTION"),
        host=os.getenv("CHROMA_HOST"),
        port=os.getenv("CHROMA_PORT"),
        llm_api_key=os.getenv("GROQ_API_KEY"),
        embedding_api_key=os.getenv("OPENAI_API_KEY"),
    )

    # Check for required arguments
    if len(sys.argv) < 3:
        print("Usage: python rag_evaluator.py <pipeline_name> <experiment_name>")
        print("Example: python rag_evaluator.py CRAGPipeline rag_eval_CRAGPipeline")
        sys.exit(1)

    # Get pipeline name and experiment name from arguments
    pipeline_name = sys.argv[1]
    experiment_name = sys.argv[2]
    
    print(f"Using pipeline: {pipeline_name}")
    print(f"Using experiment name: {experiment_name}")
    
    rag_config_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "backend", "app", "rag", pipeline_name + ".py"
        )
    )

    try:
        # Load the pipeline class
        Pipeline = get_class_from_input(rag_config_path, pipeline_name)
        print(f"Successfully loaded pipeline: {pipeline_name}")

        # Initialize RAG pipeline
        rag_pipeline = Pipeline(config)

        # Initialize evaluator
        evaluator = RAGEvaluator(test_dataset_path, rag_pipeline)

        # Always run full evaluation with provided experiment name
        print(f"Running full evaluation with experiment name: {experiment_name}")
        results = evaluator.run_full_evaluation(experiment_name)

        print("\nEvaluation Results:")
        print(json.dumps(results, indent=2))

        # Run bias analysis
        print("\nRunning bias analysis...")
        bias_analyzer = RAGBiasAnalyzer(evaluator)
        bias_report = bias_analyzer.generate_bias_report(experiment_name=experiment_name)
        print("\nBias Analysis Report:")
        print(json.dumps(bias_report, indent=2))

        # Save results to database if performance meets threshold
        try:
            thresholds = {
                'embedding_evaluation': {
                    'retrieval_precision': 0.2,
                    'retrieval_recall': 0.2,
                    'retrieval_f1': 0.2
                },
                'top_k_evaluation': {
                    'top_k_1': 0.2,
                    'top_k_3': 0.2,
                    'top_k_5': 0.2
                },
                'rag_system_evaluation': {
                    'bleu_score': 0.2,
                    'llm_judge_accuracy': 0.2,
                    'llm_judge_relevance': 0.2,
                    'llm_judge_completeness': 0.2
                }
            }
            llms = check_llm_results(results, thresholds)
            
            # Create database session
            DB_USER = os.getenv("DB_USER")
            DB_PASSWORD = os.getenv("DB_PASSWORD")
            DB_HOST = os.getenv("DB_HOST")
            DB_PORT = os.getenv("DB_PORT")
            DB_NAME = os.getenv("DB_NAME")
            
            if all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
                engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
                Session = sessionmaker(bind=engine)
                session = Session()
                        
                # Check if RAG model already exists in database
                existing_rag = session.query(RAG).filter_by(rag_name=pipeline_name).first()              
                if llms["overall_pass"]:
                    if existing_rag:
                        # Update existing RAG model
                        existing_rag.is_available = True
                        session.commit()
                        print(f"Updated existing RAG model '{pipeline_name}' in database with True availability")
                    else:
                        # Add new RAG model to database
                        new_rag = RAG(
                            rag_id=uuid.uuid4(),
                            rag_name=pipeline_name,
                            is_available=True
                        )
                        session.add(new_rag)
                        print(f"RAG model '{pipeline_name}' added to database with True availability")
                else:
                    if existing_rag:
                        # Update existing RAG model
                        existing_rag.is_available = False
                        session.commit()
                        print(f"Updated existing RAG model '{pipeline_name}' in database with False availability")
                    else:
                        # Add new RAG model to database
                        new_rag = RAG(
                            rag_id=uuid.uuid4(),
                            rag_name=pipeline_name,
                            is_available=False
                        )
                        session.add(new_rag)
                        print(f"RAG model '{pipeline_name}' added to database with False availability")
                session.close()
            else:
                print("Warning: Database credentials not fully configured. Skipping database update.")
                
        except Exception as e:
            print(f"Warning: Failed to update database: {str(e)}")
            traceback.print_exc()

    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
