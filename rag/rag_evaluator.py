import os
import sys
import json
import numpy as np
import pandas as pd
import mlflow
import chromadb
import importlib
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Tuple, Callable, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

from RAGConfig import RAGConfig
from RAGEvaluator import RAGEvaluator

load_dotenv()

# Initialize MLflow
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))

# Set authentication if you enabled it
mlflow.set_tracking_username(os.getenv("MLFLOW_USERNAME"))
mlflow.set_tracking_password(os.getenv("MLFLOW_PASSWORD"))

def get_class_from_input(module_name, class_name):
    """
    Dynamically imports a class from a module specified by string input.

    Args:
        module_name (str): The name of the module to import (e.g., "my_module").
        class_name (str): The name of the class to retrieve (e.g., "MyClass").

    Returns:
        type: The class object if found, otherwise None.
    """
    try:
        module = importlib.import_module(module_name)
        target_class = getattr(module, class_name)
        return target_class
    except (ImportError, AttributeError) as e:
        print(e)
        return None

def main():
    print(sys.argv)
    if len(sys.argv) == 3:
        test_dataset_path = os.getenv("TEST_DATASET_PATH")
        
        # Define RAG configuration
        config = RAGConfig(
            embedding_model=os.getenv("EMBEDDING_MODEL"),
            llm_model=os.getenv("LLM_MODEL"),
            top_k=int(os.getenv("TOP_K")),
            temperature=float(os.getenv("TEMPERATURE")),
            collection_name=os.getenv("CHROMA_COLLECTION"),
            host=os.getenv("CHROMA_HOST"),
            port=os.getenv("CHROMA_PORT"),
            llm_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        Pipeline = get_class_from_input(sys.argv[1], sys.argv[1])
        print(Pipeline)
        if Pipeline:
            # Initialize RAG pipeline
            rag_pipeline = Pipeline(config)
            
            # Initialize evaluator
            evaluator = RAGEvaluator(test_dataset_path, rag_pipeline)
            
            # Run evaluation
            results = evaluator.run_full_evaluation(sys.argv[2])
    else:
        print("Please provide the rag pipeline name and test run name as command line argument.")


if __name__ == "__main__":
    main()