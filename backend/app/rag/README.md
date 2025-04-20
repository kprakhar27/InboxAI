# RAG Pipeline

## Overview

This folder contains various implementations of Retrieval-Augmented Generation (RAG) pipelines, including Simple RAG and Conditional RAG (CRAG) pipelines. These pipelines are designed to evaluate the performance of RAG systems and log the results to an MLflow server for tracking and analysis.

## CI/CD Integration

The CI/CD GitHub Action for this project can be found at [`.github/workflows/test-rag.yml`](../.github/workflows/test-rag.yml). The select best model included in the CI/CD action file.

## Folder Structure

```
Directory structure:

└── rag/
    ├── README.md                             # Documentation for the RAG pipeline project
    ├── CRAGPipeline.py                       # Implementation of the Conditional RAG (CRAG) pipeline with MLflow integration
    ├── models.py                             # Contains model definitions and utilities
    ├── rag_evaluator.py                      # Script to initialize and run evaluations on the RAG pipelines
    ├── RAGBiasAnalyzer.py                    # Logic to check the bias across different Email topics
    ├── RAGConfig.py                          # Configuration file for the RAG pipelines
    ├── RAGEvaluator.py                       # Contains the RAGEvaluator class to evaluate RAG pipelines and log results to MLflow
    ├── RAGPipeline.py                        # Implementation of the Simple RAG pipeline with MLflow integration
    ├── requirements.txt                      # List of required Python packages
    ├── __init__.py                           # Package initialization file
    └── synthetic_validation_data/
        ├── question-generation-retrieval-evaluation.ipynb  # Notebook for question generation and retrieval evaluation
        ├── question_generation_retrieval_evaluation.py     # Script for question generation and retrieval evaluation
        └── synthetic_email_generator.py                    # Code to generate synthetic emails for evaluation and bias detection
```

- **RAGPipeline.py**: Contains the implementation of the Simple RAG pipeline with MLflow integration.
- **CRAGPipeline.py**: Contains the implementation of the Conditional RAG (CRAG) pipeline with MLflow integration.
- **RAGBiasAnalyzer.py**: Contains the logic to check the bias across different Email topics.
- **rag_evaluator.py**: Script to initialize and run evaluations on the RAG pipelines.
- **RAGConfig.py**: Configuration file for the RAG pipelines.
- **RAGEvaluator.py**: Contains the `RAGEvaluator` class, which evaluates the performance of the RAG pipelines and logs the results to MLflow.
- **synthetic_email_generator.py**: Code used to generate synthetic emails for evaluation and bias detection.
- **__init__.py**: Package initialization file for importing the RAG modules.

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
    GROQ_API_KEY=<your_groq_api_key>
    TEST_DATASET_PATH=<path_to_test_dataset>
    EMBEDDING_MODEL=text-embedding-3-small
    LLM_MODEL=mixtral-8x7b-32768
    TOP_K=3
    TEMPERATURE=0.7
    CHROMA_COLLECTION=test   # for general testing purposes
    CHROMA_HOST=<chroma_host>
    CHROMA_PORT=<chroma_port>
    ```

### Running Evaluations

1. **CRAG Pipeline Evaluation**:
    ```sh
    python rag_evaluator.py CRAGPipeline `experiment_name`
    ```

2. **General RAG Evaluation**:
    ```sh
    python rag_evaluator.py RAGPipeline `experiment_name`
    ```

3. **Evaluation with Bias Analysis**:
    ```sh
    python rag_evaluator.py `pipeline_name` `experiment_name` `bias_analysis_name`
    ```

### Running Bias Evaluation

**For any topic out of the topics that we created emails for**:
```sh
python rag_evaluator.py `pipeline_name` `topic` `experiment_name`
```

**To use the `RAGBiasAnalyzer`, initialize it with an instance of `RAGEvaluator` and call the `generate_bias_report` method**:

```python
bias_analyzer = RAGBiasAnalyzer(rag_evaluator)
bias_report = bias_analyzer.generate_bias_report()
```

### Logging Results

The results of the evaluations are logged to the MLflow server specified in the `.env` file. You can view the logged metrics and parameters by accessing your MLflow server.

## RAG Architecture

### Data Models

The RAG system uses several data models defined in `models.py`:

1. **GraphState**: Represents the state of the RAG graph with:
   - `question`: The user's question
   - `generation`: LLM-generated response
   - `documents`: List of retrieved documents

2. **HybridGraphState**: Extends GraphState for hybrid RAG with:
   - `keyword_docs`: Documents retrieved via keyword search
   - `vector_docs`: Documents retrieved via vector search
   - `reranked_docs`: Documents after reranking

3. **RetrievalEvaluator**: Classifies retrieved documents based on relevance to the user's question.

### Configuration

The `RAGConfig` class in `RAGConfig.py` defines the configuration for RAG pipelines:

```python
@dataclass
class RAGConfig:
    embedding_model: str      # Model for generating embeddings
    llm_model: str            # Language model for generation
    top_k: int                # Number of documents to retrieve
    temperature: float        # Temperature for LLM generation
    collection_name: str      # ChromaDB collection name
    host: str                 # ChromaDB host
    port: str                 # ChromaDB port
    llm_api_key: str          # API key for LLM service
    embedding_api_key: str    # API key for embedding service
```

### Evaluation Process

The evaluation process is managed by the `rag_evaluator.py` script, which:

1. Loads configuration from environment variables
2. Dynamically imports the specified RAG pipeline class
3. Initializes the pipeline with the configuration
4. Creates an evaluator instance with the pipeline
5. Runs the evaluation and logs results to MLflow
6. Optionally performs bias analysis and saves the report

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

### RAGBiasAnalyzer

- **analyze_topic_bias() -> Dict[str, Any]**: Analyzes potential bias across different topics and industries, returning a dictionary of bias analysis results.
- **_analyze_subset_bias(cases: List[Dict], subset_type: str) -> Dict[str, float]**: Analyzes bias for a subset of test cases, calculating metrics such as accuracy, relevance, and completeness.
- **_calculate_bias_indicators(topic_results: Dict, industry_results: Dict) -> Dict[str, float]**: Calculates overall bias indicators by analyzing the variance in accuracy, relevance, and completeness across topics and industries.
- **generate_bias_report(experiment_name: str = "RAG_Bias_Analysis") -> Dict[str, Any]**: Generates a comprehensive bias analysis report, logging the results to MLflow.

## API Integration

The RAG pipelines are integrated with a Flask-based REST API in the main application. The API endpoints are defined in `backend/app/routes/api.py`.

### Available Endpoints

#### 1. Get RAG Sources

```
GET /api/ragsources
```

Returns a list of available RAG sources with their IDs and names.

**Response**:
```json
{
  "sources": [
    {"rag_id": "uuid-string", "name": "RAGPipeline"},
    {"rag_id": "uuid-string", "name": "CRAGPipeline"}
  ],
  "total": 2
}
```

#### 2. Get Inference

```
POST /api/getinference
```

Processes a query using the specified RAG pipeline and returns a response.

**Request Body**:
```json
{
  "query": "text of the question",
  "chat_id": "uuid-string",
  "rag_id": "uuid-string"
}
```

**Response**:
```json
{
  "message_id": "uuid-string",
  "response": "Generated response text",
  "rag_id": "uuid-string",
  "query": "Original query text",
  "response_time_ms": 1234,
  "is_toxic": false
}
```

### Authentication

All API endpoints require JWT authentication. Include the JWT token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

### Error Handling

The API returns appropriate HTTP status codes and error messages:

- **400 Bad Request**: Missing required fields or invalid input
- **401 Unauthorized**: Missing or invalid JWT token
- **404 Not Found**: User, chat, or RAG source not found
- **500 Internal Server Error**: Server-side error

## Example Usage

### Basic Usage

```python
from CRAGPipeline import CRAGPipeline
from RAGConfig import RAGConfig

# Initialize configuration
config = RAGConfig(
    embedding_model="text-embedding-3-small",
    llm_model="mixtral-8x7b-32768",
    top_k=3,
    temperature=0.7,
    collection_name="your_collection",
    host="chroma-hostname",
    port='chroma-port',
    llm_api_key="your_groq_api_key",
    embedding_api_key="your_openai_api_key"
)

# Create pipeline
pipeline = CRAGPipeline(config)

# Process a query
result = pipeline.query(
    query="What is the capital of France?",
    history="Previous conversation context...",
    relevant_docs=None
)

print(result["response"])
```

### Running the Example Script

The repository includes an example script that demonstrates how to use the Conditional RAG pipeline:

```bash
python example_usage.py
```

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

### Generating Synthetic Data

You can generate your own synthetic data using the provided scripts:

```python
from synthetic_validation_data.synthetic_email_generator import generate_synthetic_emails
from synthetic_validation_data.question_generation_retrieval_evaluation import generate_questions

# Generate synthetic emails
emails = generate_synthetic_emails(num_emails=100)

# Generate questions from emails
questions = generate_questions(emails, num_questions=50)
```

## Question Generation and Retrieval Evaluation

The `question-generation-retrieval-evaluation.ipynb` notebook provides a comprehensive framework for:

1. **Automatic Question Generation**: Generates meaningful questions from the dataset using LLM-based techniques to create a diverse evaluation set.

2. **Retrieval Performance Analysis**: Evaluates how effectively each RAG implementation retrieves relevant context for generated questions.

3. **Metrics Visualization**: Contains visualizations for:
    - Retrieval precision/recall
    - Answer relevance
    - Context utilization
    - Response latency

4. **Pipeline Comparison**: Side-by-side comparison of Simple RAG and CRAG approaches on the same test cases.

5. **Error Analysis**: Detailed breakdown of failure cases to identify improvement opportunities.

Use this notebook to:
- Generate custom evaluation questions from your dataset
- Benchmark different retrieval strategies
- Visualize performance metrics across models
- Identify specific areas for pipeline optimization

These categories can be used to detect bias in the output generation process.

## Dependencies

The project relies on the following key dependencies:

- **chromadb**: Vector database for document storage and retrieval
- **langchain**: Framework for building LLM applications
- **langchain-openai**: OpenAI integration for LangChain
- **langgraph**: Graph-based workflow for LLM applications
- **openai**: OpenAI API client
- **pandas & numpy**: Data manipulation and analysis
- **pydantic**: Data validation
- **fastapi & uvicorn**: API framework and server
- **nltk & spacy**: Natural language processing
- **mlflow**: Experiment tracking and model management
- **scikit-learn**: Machine learning utilities

See `requirements.txt` for the complete list of dependencies and their versions.
