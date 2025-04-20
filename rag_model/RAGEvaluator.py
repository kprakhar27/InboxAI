import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import mlflow
import pandas as pd
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity


class RAGEvaluator:
    """Evaluator for RAG pipelines"""
    
    def __init__(self, test_dataset_path: str, rag_pipeline):
        """
        Initialize evaluator with test dataset
        
        Args:
            test_dataset_path: Path to test dataset with format:
                [
                    {
                        "query": "...",
                        "ground_truth": "...",
                        "relevant_docs": ["...", ...] (optional)
                    },
                    ...
                ]
        """
        self.test_dataset = self._load_test_dataset(test_dataset_path)
        self.rag_pipeline = rag_pipeline
        self.client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=self.rag_pipeline.config.llm_api_key)
        
    def _load_test_dataset(self, path: str) -> List[Dict[str, Any]]:
        """Load test dataset from file"""
        with open(path, 'r') as f:
            return json.load(f)
    
    def evaluate_embedding_model(self) -> Dict[str, float]:
        """Evaluate embedding model quality"""
        results = {}
        
        retrieval_precision_sum = 0
        retrieval_recall_sum = 0
        retrieval_f1_sum = 0
        
        for i, test_case in enumerate(self.test_dataset):
            query = test_case["query"]
            
            # Skip if no ground truth relevant docs
            if "relevant_docs" not in test_case:
                continue
                
            ground_truth_docs = set(test_case["relevant_docs"])
            
            # Get retrieved docs
            retrieved_docs = set(self.rag_pipeline.semantic_search(query))
            
            # Calculate precision and recall
            if len(retrieved_docs) > 0:
                precision = len(ground_truth_docs.intersection(retrieved_docs)) / len(retrieved_docs)
            else:
                precision = 0
                
            if len(ground_truth_docs) > 0:
                recall = len(ground_truth_docs.intersection(retrieved_docs)) / len(ground_truth_docs)
            else:
                recall = 0
                
            # Calculate F1
            if precision + recall > 0:
                f1 = 2 * precision * recall / (precision + recall)
            else:
                f1 = 0
                
            retrieval_precision_sum += precision
            retrieval_recall_sum += recall
            retrieval_f1_sum += f1
        
        num_cases = len(self.test_dataset)
        results["retrieval_precision"] = retrieval_precision_sum / num_cases
        results["retrieval_recall"] = retrieval_recall_sum / num_cases
        results["retrieval_f1"] = retrieval_f1_sum / num_cases
        
        return results
    
    def evaluate_top_k_strategy(self, k_values: List[int]) -> Dict[str, Dict[str, float]]:
        """Evaluate different top-k retrieval strategies"""
        results = {}
        
        for k in k_values:
            with mlflow.start_run(nested=True, run_name=f"top_k_{k}"):
                mlflow.log_param("top_k", k)
                
                accuracy_sum = 0
                
                for test_case in self.test_dataset:
                    query = test_case["query"]
                    ground_truth = test_case["ground_truth"]
                    
                    # Get retrieved docs with specific k
                    retrieved_docs = self.rag_pipeline.semantic_search(query, k=k)
                    
                    # Generate response with these docs
                    response = self.rag_pipeline.generate_response(query, retrieved_docs)
                    
                    # Evaluate answer quality using LLM as judge
                    accuracy = self._llm_judge_answer_quality(response, ground_truth)
                    accuracy_sum += accuracy
                    
                avg_accuracy = accuracy_sum / len(self.test_dataset)
                mlflow.log_metric("answer_accuracy", avg_accuracy)
                
                results[f"top_k_{k}"] = {"answer_accuracy": avg_accuracy}
        
        return results
    
    def _llm_judge_answer_quality(self, response: str, ground_truth: str) -> float:
        """Use LLM as judge to evaluate answer quality"""
        prompt = f"""
            On a scale of 0 to 1, how accurately does the following answer address the question compared to the ground truth?

            Ground Truth Answer: {ground_truth}

            Generated Answer: {response}

            Score only the factual accuracy and relevance, not writing style or verbosity. 
            Return only a single number between 0 and 1, where:
            0 = completely incorrect or irrelevant
            1 = perfectly accurate and relevant
        """
        
        judge_response = self.client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        # Extract score from response
        try:
            score = float(judge_response.choices[0].message.content.strip())
            return min(max(score, 0.0), 1.0)  # Ensure score is in [0,1]
        except ValueError:
            # If can't parse as float, use a default
            return 0.5
    
    def evaluate_rag_system(self) -> Dict[str, float]:
        """Evaluate full RAG system using mlflow.evaluate()"""
        results = {}
        
        # Run full pipeline on test dataset
        predictions = []
        ground_truths = []
        
        for test_case in self.test_dataset:
            query = test_case["query"]
            ground_truth = test_case["ground_truth"]
            
            rag_result = self.rag_pipeline.query(query)
            
            predictions.append(rag_result["response"])
            ground_truths.append(ground_truth)
        
        # Convert to dataframe for mlflow
        eval_df = pd.DataFrame({
            "prediction": predictions,
            "target": ground_truths
        })
        
        # Basic metrics
        with mlflow.start_run(nested=True, run_name="rag_evaluation"):
            # Calculate metric: BLEU score
            import nltk
            from nltk.translate.bleu_score import SmoothingFunction, corpus_bleu
            nltk.download('punkt', quiet=True)
            nltk.download('punkt_tab', quiet=True)
            
            # Tokenize predictions and references
            tokenized_predictions = [nltk.word_tokenize(pred.lower()) for pred in predictions]
            tokenized_references = [[nltk.word_tokenize(ref.lower())] for ref in ground_truths]
            
            # Calculate BLEU score
            smoothing = SmoothingFunction().method1
            bleu_score = corpus_bleu(tokenized_references, tokenized_predictions, smoothing_function=smoothing)
            
            mlflow.log_metric("bleu_score", bleu_score)
            results["bleu_score"] = bleu_score
            
            # LLM as judge metrics
            accuracy_sum = 0
            relevance_sum = 0
            completeness_sum = 0
            
            for pred, truth in zip(predictions, ground_truths):
                # Accuracy
                accuracy = self._llm_judge_answer_quality(pred, truth)
                accuracy_sum += accuracy
                
                # Relevance
                relevance = self._llm_judge_answer_relevance(pred, truth)
                relevance_sum += relevance
                
                # Completeness
                completeness = self._llm_judge_answer_completeness(pred, truth)
                completeness_sum += completeness
            
            num_examples = len(predictions)
            avg_accuracy = accuracy_sum / num_examples
            avg_relevance = relevance_sum / num_examples
            avg_completeness = completeness_sum / num_examples
            
            mlflow.log_metric("llm_judge_accuracy", avg_accuracy)
            mlflow.log_metric("llm_judge_relevance", avg_relevance)
            mlflow.log_metric("llm_judge_completeness", avg_completeness)
            
            results["llm_judge_accuracy"] = avg_accuracy
            results["llm_judge_relevance"] = avg_relevance
            results["llm_judge_completeness"] = avg_completeness
        
        return results
    
    def _llm_judge_answer_relevance(self, response: str, ground_truth: str) -> float:
        """Judge how relevant the answer is to the implied question"""
        prompt = f"""
            On a scale of 0 to 1, how relevant is the following answer to the question implied by the ground truth?

            Ground Truth Answer: {ground_truth}

            Generated Answer: {response}

            Return only a single number between 0 and 1, where:
            0 = completely irrelevant
            1 = perfectly relevant
        """
        
        judge_response = self.client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        try:
            score = float(judge_response.choices[0].message.content.strip())
            return min(max(score, 0.0), 1.0)
        except ValueError:
            return 0.5
    
    def _llm_judge_answer_completeness(self, response: str, ground_truth: str) -> float:
        """Judge how complete the answer is compared to ground truth"""
        prompt = f"""
            On a scale of 0 to 1, how complete is the following answer compared to the ground truth?

            Ground Truth Answer: {ground_truth}

            Generated Answer: {response}

            Return only a single number between 0 and 1, where:
            0 = completely incomplete (missing critical information)
            1 = perfectly complete (covers all important information)
        """
        
        judge_response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        try:
            score = float(judge_response.choices[0].message.content.strip())
            return min(max(score, 0.0), 1.0)
        except ValueError:
            return 0.5
    
    def run_full_evaluation(self, experiment_name: str) -> Dict[str, Any]:
        """Run all evaluations"""
        mlflow.set_experiment(experiment_name)
        
        with mlflow.start_run(run_name="full_evaluation"):
            # Log RAG configuration
            mlflow.log_params({
                "embedding_model": self.rag_pipeline.config.embedding_model,
                "llm_model": self.rag_pipeline.config.llm_model,
                "top_k": self.rag_pipeline.config.top_k,
                "temperature": self.rag_pipeline.config.temperature
            })
            
            # Evaluate embedding model
            print("Evaluating embedding model...")
            embedding_results = self.evaluate_embedding_model()
            for metric, value in embedding_results.items():
                mlflow.log_metric(metric, value)
            
            # Evaluate top-k strategies
            print("Evaluating top-k strategies...")
            top_k_results = self.evaluate_top_k_strategy( 
                k_values=[1, 3, 5, 10]
            )
            
            # Evaluate full RAG system
            print("Evaluating full RAG system...")
            rag_results = self.evaluate_rag_system()
            for metric, value in rag_results.items():
                mlflow.log_metric(metric, value)
            
            all_results = {
                "embedding_evaluation": embedding_results,
                "top_k_evaluation": top_k_results,
                "rag_evaluation": rag_results
            }
            
            return all_results
