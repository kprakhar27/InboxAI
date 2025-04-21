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
    """Check if LLM evaluation results exceed given thresholds with debug prints."""

    def check_overall(metrics, threshold_metrics, category_name):
        """Compare each metric with its threshold and print debug info."""
        all_pass = True
        for key, threshold_val in threshold_metrics.items():
            actual_val = metrics.get(key, 0)
            if actual_val >= threshold_val:
                print(f"[PASS ✅] {category_name} → {key}: {actual_val:.3f} >= {threshold_val:.3f}")
            else:
                print(f"[FAIL ❌] {category_name} → {key}: {actual_val:.3f} < {threshold_val:.3f}")
                all_pass = False
        return all_pass

    # --- Embedding Evaluation ---
    embedding_metrics = results.get("embedding_evaluation", {}).get("overall", {})
    embedding_pass = check_overall(embedding_metrics, thresholds.get("embedding_evaluation", {}), "Embedding Evaluation")

    # --- Top-K Evaluation ---
    top_k_results = results.get("top_k_evaluation", {})
    top_k_pass = False
    if "error" in top_k_results:
        print("[SKIP ⚠️] Top-K Evaluation skipped due to error:", top_k_results["error"])
    else:
        top_k_pass = True
        for k, threshold_val in thresholds["top_k_evaluation"].items():
            actual_val = top_k_results.get(k, {}).get("overall", {}).get("answer_accuracy", 0)
            if actual_val >= threshold_val:
                print(f"[PASS ✅] Top-K Evaluation → {k} accuracy: {actual_val:.3f} >= {threshold_val:.3f}")
            else:
                print(f"[FAIL ❌] Top-K Evaluation → {k} accuracy: {actual_val:.3f} < {threshold_val:.3f}")
                top_k_pass = False

    # --- RAG System Evaluation ---
    rag_metrics = results.get("rag_system_evaluation", {}).get("overall", {})
    rag_pass = check_overall(rag_metrics, thresholds.get("rag_system_evaluation", {}), "RAG System Evaluation")

    overall = embedding_pass or top_k_pass or rag_pass
    print(f"\n🔍 Summary:\n  Embedding Pass: {embedding_pass}\n  Top-K Pass: {top_k_pass}\n  RAG Pass: {rag_pass}\n  ✅ Overall Pass: {overall}")
    
    return {
        "embedding_pass": embedding_pass,
        "top_k_pass": top_k_pass,
        "rag_pass": rag_pass,
        "overall_pass": overall
    }


def main():
    print(sys.argv)

    # Get test dataset path from environment
    test_dataset_path = os.getenv("TEST_DATASET_PATH", )
    print(f"Test dataset path: {test_dataset_path}")

    # Define RAG configuration
    config = RAGConfig(
        embedding_model=os.getenv("EMBEDDING_MODEL"),
        llm_model=os.getenv("LLM_MODEL"),
        top_k=int(os.getenv("TOP_K")),
        temperature=float(os.getenv("TEMPERATURE")),
        collection_name=os.getenv("CHROMA_COLLECTION"),
        host=os.getenv("CHROMA_HOST"),
        port=os.getenv("CHROMA_PORT"),
        llm_api_key=os.getenv("GROQ_API_KEY"),
        embedding_api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    rag_config_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "backend", "app", "rag", sys.argv[1] + ".py"
        )
    )

    # Handle different argument scenarios
    if len(sys.argv) == 3:
        
        # Original 2-argument scenario (pipeline name and run name)
        Pipeline = get_class_from_input(rag_config_path, sys.argv[1])
        print(Pipeline)

        if Pipeline:
            # Initialize RAG pipeline
            rag_pipeline = Pipeline(config)

            # Initialize evaluator
            evaluator = RAGEvaluator(test_dataset_path, rag_pipeline)

            # Run evaluation
            results = evaluator.run_full_evaluation(sys.argv[2])
            
            print(results)
            
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
                engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
                Session = sessionmaker(bind=engine)
                session = Session()
                        
                # Check if RAG model already exists in database
                existing_rag = session.query(RAG).filter_by(rag_name=sys.argv[1]).first()              
                if llms["overall_pass"]:
                    if existing_rag:
                        # Update existing RAG model
                        existing_rag.is_available = True
                        session.commit()
                        print(f"Updated existing RAG model '{sys.argv[1]}' in database with True availability")
                    else:
                        # Add new RAG model to database
                        new_rag = RAG(
                            rag_id=uuid.uuid4(),
                            rag_name=sys.argv[1],
                            is_available=True
                        )
                        session.add(new_rag)
                        print(f"RAG model '{sys.argv[1]}' added to database with True availability")
                else:
                    if existing_rag:
                        # Update existing RAG model
                        existing_rag.is_available = False
                        session.commit()
                        print(f"Updated existing RAG model '{sys.argv[1]}' in database with False availability")
                    else:
                        # Add new RAG model to database
                        new_rag = RAG(
                            rag_id=uuid.uuid4(),
                            rag_name=sys.argv[1],
                            is_available=False
                        )
                        session.add(new_rag)
                    print(f"RAG model '{sys.argv[1]}' added to database with False availability")
                session.commit()
                session.close()
                print("Evaluation Complete!")
            except Exception as e:
                print(f"Failed to save to database: {e}")
                traceback.print_exc()

    elif len(sys.argv) == 4:
        # New 3-argument scenario (pipeline name, eval run name, bias run name)
        Pipeline = get_class_from_input(rag_config_path, sys.argv[1])
        print(Pipeline)

        if Pipeline:
            # Initialize RAG pipeline
            rag_pipeline = Pipeline(config)

            # Initialize evaluator
            evaluator = RAGEvaluator(test_dataset_path, rag_pipeline)

            # Run full evaluation
            eval_results = evaluator.run_full_evaluation(sys.argv[2])

            # Initialize bias analyzer
            bias_analyzer = RAGBiasAnalyzer(evaluator)

            # Run bias analysis
            bias_report = bias_analyzer.generate_bias_report(
                experiment_name=sys.argv[3]
            )

            # Optional: Save bias report to a file
            with open("bias_analysis_report.json", "w") as f:
                json.dump(bias_report, f, indent=4)

            print("Evaluation and Bias Analysis Complete!")
        else:
            print(
                "Please provide the RAG pipeline name, evaluation run name, and bias analysis run name as command line arguments."
            )
    else:
        print("Usage:")
        print(
            "- For standard evaluation: python script.py <PipelineName> <EvalRunName>"
        )
        print(
            "- For evaluation with bias analysis: python script.py <PipelineName> <EvalRunName> <BiasRunName>"
        )


if __name__ == "__main__":
    main()
