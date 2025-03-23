# README

## Overview

This repository contains various implementations of Retrieval-Augmented Generation (RAG) pipelines, including Conditional RAG (CRAG) and Hybrid RAG pipelines. These pipelines are designed to evaluate the performance of RAG systems and log the results to an MLflow server for tracking and analysis.

## Folder Structure

```
.env
CRAGPipeline.py
HybridRAGPipeline.py
models.py
qa_data_mini.json
rag_evaluator.py
RAGConfig.py
RAGEvaluator.py
RAGPipeline.py
README.md
__pycache__/
```

### Key Files

- **CRAGPipeline.py**: Contains the implementation of the Conditional RAG (CRAG) pipeline with MLflow integration.
- **HybridRAGPipeline.py**: Contains the implementation of the Hybrid RAG pipeline with MLflow integration.
- **models.py**: Defines the models used in the pipelines.
- **qa_data_mini.json**: A sample dataset used for testing the pipelines.
- **rag_evaluator.py**: Script to initialize and run evaluations on the RAG pipelines.
- **RAGConfig.py**: Configuration file for the RAG pipelines.
- **RAGEvaluator.py**: Contains the `RAGEvaluator` class, which evaluates the performance of the RAG pipelines and logs the results to MLflow.
- **RAGPipeline.py**: Base class for the RAG pipeline.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Required Python packages (listed in `requirements.txt`)

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/InboxAI.git
    cd InboxAI/rag
    ```

2. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Set up the environment variables by creating a `.env` file:
    ```sh
    MLFLOW_TRACKING_URI=<your_mlflow_tracking_uri>
    MLFLOW_USERNAME=<your_mlflow_username>
    MLFLOW_PASSWORD=<your_mlflow_password>
    ```

### Running Evaluations

1. **CRAG Pipeline Evaluation**:
    ```sh
    python CRAGPipeline.py
    ```

2. **Hybrid RAG Pipeline Evaluation**:
    ```sh
    python HybridRAGPipeline.py
    ```

3. **General RAG Evaluation**:
    ```sh
    python rag_evaluator.py
    ```

### Logging Results

The results of the evaluations are logged to the MLflow server specified in the `.env` file. You can view the logged metrics and parameters by accessing your MLflow server.

## Classes and Methods

### RAGEvaluator

- **run_full_evaluation(experiment_name: str) -> Dict[str, Any]**: Runs all evaluations and logs the results to MLflow.

### RAGPipeline

- **get_embedding(text: str) -> List[float]**: Gets embeddings using the OpenAI API.
- **semantic_search(query: str, k: Optional[int] = None) -> List[str]**: Searches for the most relevant documents using ChromaDB.
- **generate_response(query: str, context: List[str]) -> str**: Generates a response using OpenAI ChatGPT.
- **query(query: str) -> Dict[str, Any]**: Completes the RAG pipeline with metadata for evaluation.

### CRAGPipeline

- **decide_to_generate(state) -> str**: Determines whether to generate an answer or re-generate a question.
- **generate_response(query: str, context: List[str]) -> str**: Generates a response using OpenAI ChatGPT.
- **query(query: str) -> Dict[str, Any]**: Completes the RAG pipeline with metadata for evaluation.

### HybridRAGPipeline

- **generate(state) -> Dict[str, Any]**: Generates an answer based on reranked documents.
- **retrieve(state) -> Dict[str, Any]**: Runs the hybrid retrieval process.
- **evaluate_documents(state) -> Dict[str, Any]**: Evaluates documents in the reranking step.
- **generate_response(query: str, context: List[str]) -> str**: Generates a response using the RAG chain.
- **query(query: str) -> Dict[str, Any]**: Completes the RAG pipeline with metadata for evaluation.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- OpenAI for the API
- MLflow for the tracking server
- ChromaDB for the document retrieval

For more information, please refer to the individual files and their respective docstrings.
