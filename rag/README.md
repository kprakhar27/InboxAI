# RAG Pipeline

## Overview

This folder contains various implementations of Retrieval-Augmented Generation (RAG) pipelines, including Simple RAG, Conditional RAG (CRAG), and Hybrid RAG pipelines. These pipelines are designed to evaluate the performance of RAG systems and log the results to an MLflow server for tracking and analysis.

## CI/CD Integration

The CI/CD GitHub Action for this project can be found at [`.github/workflows/test-rag.yml`](../.github/workflows/test-rag.yml). The select best model included in the CI/CD action file.

## Folder Structure

```
Directory structure:

└── rag/
    ├── README.md                             # Documentation for the RAG pipeline project
    ├── CRAGPipeline.py                       # Implementation of the Conditional RAG (CRAG) pipeline with MLflow integration
    ├── HybridRAGPipeline.py                  # Implementation of the Hybrid RAG pipeline with MLflow integration
    ├── models.py                             # Contains model definitions and utilities
    ├── rag_evaluator.py                      # Script to initialize and run evaluations on the RAG pipelines
    ├── RAGBiasAnalyzer.py                    # Logic to check the bias across different Email topics
    ├── RAGConfig.py                          # Configuration file for the RAG pipelines
    ├── RAGEvaluator.py                       # Contains the RAGEvaluator class to evaluate RAG pipelines and log results to MLflow
    ├── RAGPipeline.py                        # Implementation of the Simple RAG pipeline with MLflow integration
    ├── requirements.txt                      # List of required Python packages
    └── synthetic_validation_data/
        ├── question-generation-retrieval-evaluation.ipynb  # Notebook for question generation and retrieval evaluation
        ├── question_generation_retrieval_evaluation.py     # Script for question generation and retrieval evaluation
        └── synthetic_email_generator.py                    # Code to generate synthetic emails for evaluation and bias detection
```

- **RAGPipeline.py**: Contains the implementation of the Simple RAG pipeline with MLflow integration.
- **CRAGPipeline.py**: Contains the implementation of the Conditional RAG (CRAG) pipeline with MLflow integration.
- **HybridRAGPipeline.py**: Contains the implementation of the Hybrid RAG pipeline with MLflow integration.
- **RAGBiasAnalyzer.py**: Contains the logic to check the bias across different Email topics.
- **rag_evaluator.py**: Script to initialize and run evaluations on the RAG pipelines.
- **RAGConfig.py**: Configuration file for the RAG pipelines.
- **RAGEvaluator.py**: Contains the `RAGEvaluator` class, which evaluates the performance of the RAG pipelines and logs the results to MLflow.
- **synthetic_email_generator.py**: Code used to generate synthetic emails for evaluation and bias detection.

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
    OPENAI_API_KEY=<your_openai_api_key>
    TEST_DATASET_PATH=<path_to_test_dataset>
    EMBEDDING_MODEL=text-embedding-3-small
    LLM_MODEL=<gpt_model>
    TOP_K=<k>
    TEMPERATURE=<temp>
    CHROMA_COLLECTION=test   # for general testing purposes
    CHROMA_HOST=<chroma_host>
    CHROMA_PORT=<chroma_port>
    ```

### Running Evaluations

1. **CRAG Pipeline Evaluation**:
    ```sh
    python rag_evaluator.py CRAGPipeline `experiment_name`
    ```

2. **Hybrid RAG Pipeline Evaluation**:
    ```sh
    python rag_evaluator.py HybridRAGPipeline `experiment_name`
    ```

3. **General RAG Evaluation**:
    ```sh
    python rag_evaluator.py RAGPipeline `experiment_name`
    ```

### Running Bias Evaluation

**For any topic out of the topics that we created emails for**:
```sh
python rag_evaluator.py `pipeline_name` `topic` `experiment_name`
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

## Test Dataset Generation

The test dataset was generated using a combination of generative AI models and synthetic data techniques:

1. **Initial Generation**: We used OpenAI's GPT-4 to generate a diverse set of professional emails across multiple categories, including:
    - Meeting Invitations
    - Project Updates
    - Financial Reports
    - Customer Support
    - Marketing Campaigns
    - Sales Pitches
    - Technical Documentation
    - Event Invitations
    - Security Alerts

2. **Metadata Enrichment**: Each email was enriched with realistic metadata using the Faker library:
    - Sender and recipient information
    - Timestamps
    - Company names
    - Email addresses
    - CC/BCC fields

3. **Industry Diversity**: Emails were distributed across various industries:
    - Technology
    - Finance
    - Healthcare
    - Education
    - Retail
    - Government

4. **Controlled Toxicity**: A small percentage (~5%) of emails were intentionally injected with toxic content using predefined keywords to test content filtering capabilities.

5. **Format Standardization**: All emails were formatted in a consistent JSON structure with metadata, content, and analytics fields to facilitate processing and evaluation.

The final dataset comprises hundreds of realistic email examples that serve as a robust foundation for testing and evaluating our RAG systems.

## Question Generation and Retrieval Evaluation

The `question-generation-retrieval-evaluation.ipynb` notebook provides a comprehensive framework for:

1. **Automatic Question Generation**: Generates meaningful questions from the dataset using LLM-based techniques to create a diverse evaluation set.

2. **Retrieval Performance Analysis**: Evaluates how effectively each RAG implementation retrieves relevant context for generated questions.

3. **Metrics Visualization**: Contains visualizations for:
    - Retrieval precision/recall
    - Answer relevance
    - Context utilization
    - Response latency

4. **Pipeline Comparison**: Side-by-side comparison of Simple RAG, CRAG, and Hybrid RAG approaches on the same test cases.

5. **Error Analysis**: Detailed breakdown of failure cases to identify improvement opportunities.

Use this notebook to:
- Generate custom evaluation questions from your dataset
- Benchmark different retrieval strategies
- Visualize performance metrics across models
- Identify specific areas for pipeline optimization

These categories can be used to detect bias in the output generation process.
