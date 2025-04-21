# RAG Model Evaluation Framework

This folder contains tools for evaluating Retrieval-Augmented Generation (RAG) models, including performance metrics, bias analysis, and database integration.

## Overview

The RAG Model Evaluation Framework provides a comprehensive suite of tools to evaluate the performance and fairness of RAG systems. It includes:

- **RAGEvaluator**: Core evaluation engine for measuring RAG performance
- **RAGBiasAnalyzer**: Tool for detecting and analyzing biases in RAG responses
- **Database Integration**: Automatic storage of evaluation results in PostgreSQL

## Components

### RAGEvaluator

The `RAGEvaluator` class is the main evaluation engine that measures the performance of RAG systems across multiple dimensions:

- **Embedding Model Evaluation**: Measures the quality of document embeddings
- **Top-K Strategy Evaluation**: Evaluates the effectiveness of different retrieval strategies
- **RAG System Evaluation**: Assesses the overall performance of the RAG pipeline

### RAGBiasAnalyzer

The `RAGBiasAnalyzer` class analyzes potential biases in RAG responses by:

- Detecting demographic biases
- Identifying topic biases
- Measuring response diversity
- Analyzing sentiment distribution

### Database Integration

Evaluation results are automatically stored in a PostgreSQL database when performance meets predefined thresholds. The database tracks:

- RAG model availability
- Performance metrics
- Bias analysis results

## Usage

### Running the Evaluator

To run a full evaluation of a RAG model:

```bash
python rag_evaluator.py <pipeline_name> <experiment_name>
```

Example:
```bash
python rag_evaluator.py CRAGPipeline rag_eval_CRAGPipeline
```

### Environment Variables

The following environment variables must be set in your `.env` file:

```
# OpenAI API Keys
OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key

# Model Configuration
EMBEDDING_MODEL=text-embedding-ada-002
LLM_MODEL=llama3-70b-8192
TOP_K=5
TEMPERATURE=0.7

# ChromaDB Configuration
CHROMA_COLLECTION=your_collection_name
CHROMA_HOST=your_chroma_host
CHROMA_PORT=your_chroma_port

# Test Dataset
TEST_DATASET_PATH=path/to/your/test_dataset.json

# Database Configuration
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=your_db_port
DB_NAME=your_db_name

# MLflow Configuration
MLFLOW_TRACKING_URI=your_mlflow_tracking_uri
```

### Test Dataset Format

The test dataset should be a JSON file with the following structure:

```json
[
  {
    "query": "What is the capital of France?",
    "ground_truth": "The capital of France is Paris.",
    "relevant_docs": ["doc1", "doc2"],
    "topic": "geography",
    "industry": "education"
  },
  ...
]
```

## Evaluation Metrics

### Embedding Model Evaluation

- **Retrieval Precision**: Proportion of retrieved documents that are relevant
- **Retrieval Recall**: Proportion of relevant documents that are retrieved
- **Retrieval F1**: Harmonic mean of precision and recall

### Top-K Strategy Evaluation

- **Answer Accuracy**: Measures how well the retrieved documents support the correct answer
- **Relevance Score**: Measures the relevance of retrieved documents to the query

### RAG System Evaluation

- **BLEU Score**: Measures the similarity between generated and ground truth responses
- **LLM Judge Accuracy**: Human-like evaluation of answer correctness
- **LLM Judge Relevance**: Human-like evaluation of answer relevance
- **LLM Judge Completeness**: Human-like evaluation of answer completeness

### Bias Analysis

- **Demographic Bias**: Measures bias across demographic groups
- **Topic Bias**: Measures bias across different topics
- **Response Diversity**: Measures the diversity of generated responses
- **Sentiment Distribution**: Analyzes the sentiment distribution of responses

## Performance Thresholds

The following thresholds are used to determine if a RAG model meets performance requirements:

```python
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
```

## Dependencies

- Python 3.8+
- OpenAI API
- Groq API
- ChromaDB
- MLflow
- PostgreSQL
- SQLAlchemy
- NumPy
- Pandas
- scikit-learn

## License

This project is licensed under the MIT License - see the LICENSE file for details. 