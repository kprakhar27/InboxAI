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
from RAGBiasAnalyzer import RAGBiasAnalyzer
from RAGConfig import RAGConfig
from RAGEvaluator import RAGEvaluator
from sklearn.metrics.pairwise import cosine_similarity
import traceback

load_dotenv()

# Initialize MLflow
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))


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
        traceback.print_exc()
        return None


def main():
    print(sys.argv)

    # Get test dataset path from environment
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
        llm_api_key=os.getenv("GROQ_API_KEY"),
        embedding_api_key=os.getenv("OPENAI_API_KEY"),
    )

    # Handle different argument scenarios
    if len(sys.argv) == 3:
        # Original 2-argument scenario (pipeline name and run name)
        Pipeline = get_class_from_input(sys.argv[1], sys.argv[1])
        print(Pipeline)

        if Pipeline:
            # Initialize RAG pipeline
            rag_pipeline = Pipeline(config)

            # Initialize evaluator
            evaluator = RAGEvaluator(test_dataset_path, rag_pipeline)

            # Run evaluation
            results = evaluator.run_full_evaluation(sys.argv[2])

    elif len(sys.argv) == 4:
        # New 3-argument scenario (pipeline name, eval run name, bias run name)
        Pipeline = get_class_from_input(sys.argv[1], sys.argv[1])
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
