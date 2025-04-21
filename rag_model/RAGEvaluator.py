import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import defaultdict
import warnings

import mlflow
import pandas as pd
from openai import OpenAI
# Note: sklearn cosine_similarity is not used in the provided snippet
# from sklearn.metrics.pairwise import cosine_similarity

# Suppress NLTK download messages if already downloaded
os.environ['NLTK_DATA'] = os.path.join(os.path.expanduser('~'), 'nltk_data')

class RAGEvaluator:
    """
    Evaluator for RAG pipelines, including bias analysis across topics and industries.

    Assumes the test dataset includes 'topic' and 'industry' keys for each entry.
    """

    def __init__(self, test_dataset_path: str, rag_pipeline):
        """
        Initialize evaluator with test dataset.

        Args:
            test_dataset_path: Path to test dataset with format:
                [
                    {
                        "query": "...",
                        "ground_truth": "...",
                        "relevant_docs": ["...", ...], # Optional for some evals
                        "topic": "...",               # Required for bias analysis
                        "industry": "..."             # Required for bias analysis
                    },
                    ...
                ]
            rag_pipeline: An instance of the RAG pipeline to be evaluated.
                         Expected to have methods like `semantic_search(query, k=...)`,
                         `generate_response(query, docs)`, `query(query)`,
                         and a `config` attribute with relevant parameters.
        """
        self.test_dataset = self._load_test_dataset(test_dataset_path)
        self.rag_pipeline = rag_pipeline
        # Ensure API key is accessed correctly from the pipeline's config
        if not hasattr(rag_pipeline, 'config') or not hasattr(rag_pipeline.config, 'llm_api_key'):
             raise ValueError("RAG pipeline object must have a 'config' attribute with an 'llm_api_key'.")
        # Consider adding error handling for missing API key
        self.client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=self.rag_pipeline.config.llm_api_key)
        self._validate_dataset_keys()

    def _load_test_dataset(self, path: str) -> List[Dict[str, Any]]:
        """Load test dataset from JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Test dataset file not found at {path}")
            raise
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from file at {path}")
            raise

    def _validate_dataset_keys(self):
        """Check if 'topic' and 'industry' keys are present in the dataset."""
        if not self.test_dataset:
            warnings.warn("Test dataset is empty.")
            return
        
        sample_item = self.test_dataset[0]
        missing_keys = []
        if 'topic' not in sample_item:
            missing_keys.append('topic')
        if 'industry' not in sample_item:
            missing_keys.append('industry')

        if missing_keys:
            raise ValueError(f"Test dataset items are missing required keys for bias analysis: {', '.join(missing_keys)}")
        
        # Optional: Check all items, though this can be slow for large datasets
        # for i, item in enumerate(self.test_dataset):
        #     if 'topic' not in item or 'industry' not in item:
        #         warnings.warn(f"Dataset item at index {i} is missing 'topic' or 'industry'. Bias analysis might be incomplete.")


    def _safe_divide(self, numerator: float, denominator: int) -> float:
        """Helper function for safe division, returns 0 if denominator is 0."""
        return numerator / denominator if denominator > 0 else 0.0

    def evaluate_embedding_model(self) -> Dict[str, Any]:
        """
        Evaluate embedding model quality based on retrieval metrics,
        stratified by topic and industry.

        Returns:
            A dictionary containing overall and stratified retrieval metrics.
        """
        # Accumulators for overall metrics
        retrieval_precision_sum = 0
        retrieval_recall_sum = 0
        retrieval_f1_sum = 0
        num_cases_with_relevant_docs = 0

        # Accumulators for stratified metrics
        # Structure: { 'topic': { 'topic_name': {'precision_sum': 0, 'recall_sum': 0, 'f1_sum': 0, 'count': 0}, ... } }
        topic_metrics = defaultdict(lambda: defaultdict(float))
        industry_metrics = defaultdict(lambda: defaultdict(float))

        for i, test_case in enumerate(self.test_dataset):
            query = test_case.get("query")
            ground_truth_docs_list = test_case.get("relevant_docs")
            topic = test_case.get("topic")
            industry = test_case.get("industry")

            if not query or not topic or not industry:
                 warnings.warn(f"Skipping test case {i} due to missing query, topic, or industry.")
                 continue

            # Skip if no ground truth relevant docs for this test case
            if not ground_truth_docs_list:
                continue

            num_cases_with_relevant_docs += 1
            ground_truth_docs = set(ground_truth_docs_list)

            # Get retrieved docs using the default top_k from the pipeline config
            # Ensure semantic_search can handle default k
            retrieved_docs = set(self.rag_pipeline.semantic_search(query))

            # Calculate precision, recall, F1
            true_positives = len(ground_truth_docs.intersection(retrieved_docs))
            
            precision = self._safe_divide(true_positives, len(retrieved_docs))
            recall = self._safe_divide(true_positives, len(ground_truth_docs))
            f1 = self._safe_divide(2 * precision * recall, precision + recall)

            # Accumulate overall scores
            retrieval_precision_sum += precision
            retrieval_recall_sum += recall
            retrieval_f1_sum += f1

            # Accumulate scores per topic
            topic_metrics[topic]['precision_sum'] += precision
            topic_metrics[topic]['recall_sum'] += recall
            topic_metrics[topic]['f1_sum'] += f1
            topic_metrics[topic]['count'] += 1

            # Accumulate scores per industry
            industry_metrics[industry]['precision_sum'] += precision
            industry_metrics[industry]['recall_sum'] += recall
            industry_metrics[industry]['f1_sum'] += f1
            industry_metrics[industry]['count'] += 1

        # Calculate final average metrics
        results = {
            "overall": {
                "retrieval_precision": self._safe_divide(retrieval_precision_sum, num_cases_with_relevant_docs),
                "retrieval_recall": self._safe_divide(retrieval_recall_sum, num_cases_with_relevant_docs),
                "retrieval_f1": self._safe_divide(retrieval_f1_sum, num_cases_with_relevant_docs),
                "evaluated_cases_count": num_cases_with_relevant_docs
            },
            "by_topic": {},
            "by_industry": {}
        }

        for topic, metrics in topic_metrics.items():
            count = metrics['count']
            results["by_topic"][topic] = {
                "retrieval_precision": self._safe_divide(metrics['precision_sum'], count),
                "retrieval_recall": self._safe_divide(metrics['recall_sum'], count),
                "retrieval_f1": self._safe_divide(metrics['f1_sum'], count),
                "evaluated_cases_count": count
            }

        for industry, metrics in industry_metrics.items():
            count = metrics['count']
            results["by_industry"][industry] = {
                "retrieval_precision": self._safe_divide(metrics['precision_sum'], count),
                "retrieval_recall": self._safe_divide(metrics['recall_sum'], count),
                "retrieval_f1": self._safe_divide(metrics['f1_sum'], count),
                "evaluated_cases_count": count
            }

        return results

    def evaluate_top_k_strategy(self, k_values: List[int]) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate different top-k retrieval strategies based on answer accuracy,
        stratified by topic and industry.

        Args:
            k_values: A list of integers representing the top-k values to test.

        Returns:
            A nested dictionary with results for each k, including stratified metrics.
            Example: {"top_k_3": {"overall": {...}, "by_topic": {...}, "by_industry": {...}}}
        """
        results = {}

        for k in k_values:
            run_name = f"top_k_{k}"
            with mlflow.start_run(nested=True, run_name=run_name):
                mlflow.log_param("top_k", k)

                # Overall accumulators for this k
                accuracy_sum = 0
                num_cases = 0

                # Stratified accumulators for this k
                topic_metrics = defaultdict(lambda: defaultdict(float))
                industry_metrics = defaultdict(lambda: defaultdict(float))

                for i, test_case in enumerate(self.test_dataset):
                    query = test_case.get("query")
                    ground_truth = test_case.get("ground_truth")
                    topic = test_case.get("topic")
                    industry = test_case.get("industry")

                    if not query or not ground_truth or not topic or not industry:
                        warnings.warn(f"Skipping test case {i} for top_k={k} due to missing fields.")
                        continue
                    
                    num_cases += 1

                    # Get retrieved docs with specific k
                    retrieved_docs = self.rag_pipeline.semantic_search(query, k=k)

                    # Generate response with these docs
                    response = self.rag_pipeline.generate_response(query, retrieved_docs)

                    # Evaluate answer quality using LLM as judge
                    accuracy = self._llm_judge_answer_quality(response, ground_truth)
                    
                    # Accumulate overall
                    accuracy_sum += accuracy

                    # Accumulate stratified
                    topic_metrics[topic]['accuracy_sum'] += accuracy
                    topic_metrics[topic]['count'] += 1
                    industry_metrics[industry]['accuracy_sum'] += accuracy
                    industry_metrics[industry]['count'] += 1

                # Calculate and log overall average accuracy for this k
                avg_accuracy = self._safe_divide(accuracy_sum, num_cases)
                mlflow.log_metric("answer_accuracy_overall", avg_accuracy)

                k_results = {
                    "overall": {"answer_accuracy": avg_accuracy, "evaluated_cases_count": num_cases},
                    "by_topic": {},
                    "by_industry": {}
                }

                # Calculate, log, and store stratified results for this k
                for topic, metrics in topic_metrics.items():
                    count = metrics['count']
                    avg_topic_accuracy = self._safe_divide(metrics['accuracy_sum'], count)
                    mlflow.log_metric(f"answer_accuracy_topic_{topic}", avg_topic_accuracy)
                    k_results["by_topic"][topic] = {"answer_accuracy": avg_topic_accuracy, "evaluated_cases_count": count}

                for industry, metrics in industry_metrics.items():
                    count = metrics['count']
                    avg_industry_accuracy = self._safe_divide(metrics['accuracy_sum'], count)
                    mlflow.log_metric(f"answer_accuracy_industry_{industry}", avg_industry_accuracy)
                    k_results["by_industry"][industry] = {"answer_accuracy": avg_industry_accuracy, "evaluated_cases_count": count}

                results[run_name] = k_results

        return results

    def _llm_judge_answer_quality(self, response: str, ground_truth: str) -> float:
        """Use LLM as judge to evaluate answer quality (factual accuracy/relevance)."""
        prompt = f"""
            On a scale of 0 to 1, how accurately does the following answer address the question compared to the ground truth?

            Ground Truth Answer: {ground_truth}

            Generated Answer: {response}

            Score only the factual accuracy and relevance, not writing style or verbosity.
            Return only a single floating-point number between 0.0 and 1.0.
            Examples: 0.0, 0.25, 0.5, 0.75, 1.0
        """
        try:
            judge_response = self.client.chat.completions.create(
                model="llama3-8b-8192", # Ensure this model is available via Groq
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10 # Restrict output length
            )
            score_str = judge_response.choices[0].message.content.strip()
            # Try to extract a number even if there's extra text
            import re
            match = re.search(r"(\d\.?\d*)", score_str)
            if match:
                score = float(match.group(1))
                return min(max(score, 0.0), 1.0)  # Clamp score to [0, 1]
            else:
                 warnings.warn(f"LLM Judge (Quality) failed to return a parseable number. Response: '{score_str}'. Defaulting to 0.5.")
                 return 0.5
        except Exception as e:
            warnings.warn(f"LLM Judge (Quality) API call failed: {e}. Defaulting to 0.5.")
            return 0.5


    def evaluate_rag_system(self) -> Dict[str, Any]:
        """
        Evaluate the full RAG system using BLEU and LLM-judged metrics,
        stratifying LLM metrics by topic and industry.

        Returns:
            A dictionary containing overall and stratified evaluation results.
            Note: BLEU score is calculated overall, not stratified per category easily.
        """
        predictions = []
        ground_truths = []
        topics = []
        industries = []

        print("Generating predictions for full RAG system evaluation...")
        for i, test_case in enumerate(self.test_dataset):
            query = test_case.get("query")
            ground_truth = test_case.get("ground_truth")
            topic = test_case.get("topic")
            industry = test_case.get("industry")

            if not query or not ground_truth or not topic or not industry:
                 warnings.warn(f"Skipping test case {i} for full RAG eval due to missing fields.")
                 continue

            try:
                # Assuming rag_pipeline.query returns a dict like {"response": "..."}
                rag_result = self.rag_pipeline.query(query)
                predictions.append(rag_result.get("response", "")) # Handle missing response
                ground_truths.append(ground_truth)
                topics.append(topic)
                industries.append(industry)
            except Exception as e:
                 warnings.warn(f"Error processing query for test case {i}: {e}. Skipping.")
                 continue # Skip this test case if pipeline fails

        if not predictions:
             print("No predictions were generated. Cannot evaluate RAG system.")
             return {"error": "No predictions generated."}

        results = {
            "overall": {},
            "by_topic": defaultdict(lambda: defaultdict(float)),
            "by_industry": defaultdict(lambda: defaultdict(float))
        }
        num_examples = len(predictions)

        # --- Overall Metrics ---
        with mlflow.start_run(nested=True, run_name="rag_full_evaluation"):
            # 1. BLEU Score (Overall)
            try:
                import nltk
                from nltk.translate.bleu_score import SmoothingFunction, corpus_bleu
                # Attempt to download punkt quietly, handle potential errors
                try:
                    nltk.download('punkt', quiet=True, download_dir=os.environ['NLTK_DATA'])
                except Exception as e:
                    warnings.warn(f"NLTK punkt download failed: {e}. BLEU score calculation might fail.")

                tokenized_predictions = [nltk.word_tokenize(pred.lower()) for pred in predictions]
                tokenized_references = [[nltk.word_tokenize(ref.lower())] for ref in ground_truths]

                smoothing = SmoothingFunction().method1
                bleu_score = corpus_bleu(tokenized_references, tokenized_predictions, smoothing_function=smoothing)

                mlflow.log_metric("bleu_score_overall", bleu_score)
                results["overall"]["bleu_score"] = bleu_score
            except ImportError:
                warnings.warn("NLTK not installed. Skipping BLEU score calculation. Install with: pip install nltk")
                results["overall"]["bleu_score"] = None
            except Exception as e:
                 warnings.warn(f"BLEU score calculation failed: {e}")
                 results["overall"]["bleu_score"] = None


            # 2. LLM as Judge Metrics (Overall and Stratified)
            print("Evaluating generated responses using LLM judge...")
            accuracy_sum, relevance_sum, completeness_sum = 0, 0, 0
            # Use temporary dicts for sums before averaging
            topic_sums = defaultdict(lambda: defaultdict(float))
            industry_sums = defaultdict(lambda: defaultdict(float))
            # Counts needed for averaging stratified results
            topic_counts = defaultdict(int)
            industry_counts = defaultdict(int)


            for i, (pred, truth, topic, industry) in enumerate(zip(predictions, ground_truths, topics, industries)):
                if i % 10 == 0: # Print progress
                     print(f"  Judging response {i+1}/{num_examples}...")
                # Accuracy
                accuracy = self._llm_judge_answer_quality(pred, truth)
                accuracy_sum += accuracy
                topic_sums[topic]['accuracy_sum'] += accuracy
                industry_sums[industry]['accuracy_sum'] += accuracy

                # Relevance
                relevance = self._llm_judge_answer_relevance(pred, truth) # Assuming query implied by truth
                relevance_sum += relevance
                topic_sums[topic]['relevance_sum'] += relevance
                industry_sums[industry]['relevance_sum'] += relevance

                # Completeness
                completeness = self._llm_judge_answer_completeness(pred, truth)
                completeness_sum += completeness
                topic_sums[topic]['completeness_sum'] += completeness
                industry_sums[industry]['completeness_sum'] += completeness

                # Increment counts for averaging
                topic_counts[topic] += 1
                industry_counts[industry] += 1

            # Calculate and log overall averages
            avg_accuracy = self._safe_divide(accuracy_sum, num_examples)
            avg_relevance = self._safe_divide(relevance_sum, num_examples)
            avg_completeness = self._safe_divide(completeness_sum, num_examples)

            mlflow.log_metric("llm_judge_accuracy_overall", avg_accuracy)
            mlflow.log_metric("llm_judge_relevance_overall", avg_relevance)
            mlflow.log_metric("llm_judge_completeness_overall", avg_completeness)

            results["overall"]["llm_judge_accuracy"] = avg_accuracy
            results["overall"]["llm_judge_relevance"] = avg_relevance
            results["overall"]["llm_judge_completeness"] = avg_completeness
            results["overall"]["evaluated_cases_count"] = num_examples


            # Calculate, log, and store stratified results
            print("Calculating stratified LLM judge metrics...")
            for topic, t_sums in topic_sums.items():
                count = topic_counts[topic]
                avg_topic_accuracy = self._safe_divide(t_sums['accuracy_sum'], count)
                avg_topic_relevance = self._safe_divide(t_sums['relevance_sum'], count)
                avg_topic_completeness = self._safe_divide(t_sums['completeness_sum'], count)

                mlflow.log_metric(f"llm_judge_accuracy_topic_{topic}", avg_topic_accuracy)
                mlflow.log_metric(f"llm_judge_relevance_topic_{topic}", avg_topic_relevance)
                mlflow.log_metric(f"llm_judge_completeness_topic_{topic}", avg_topic_completeness)

                results["by_topic"][topic] = {
                    "llm_judge_accuracy": avg_topic_accuracy,
                    "llm_judge_relevance": avg_topic_relevance,
                    "llm_judge_completeness": avg_topic_completeness,
                    "evaluated_cases_count": count
                }

            for industry, i_sums in industry_sums.items():
                count = industry_counts[industry]
                avg_industry_accuracy = self._safe_divide(i_sums['accuracy_sum'], count)
                avg_industry_relevance = self._safe_divide(i_sums['relevance_sum'], count)
                avg_industry_completeness = self._safe_divide(i_sums['completeness_sum'], count)

                mlflow.log_metric(f"llm_judge_accuracy_industry_{industry}", avg_industry_accuracy)
                mlflow.log_metric(f"llm_judge_relevance_industry_{industry}", avg_industry_relevance)
                mlflow.log_metric(f"llm_judge_completeness_industry_{industry}", avg_industry_completeness)

                results["by_industry"][industry] = {
                    "llm_judge_accuracy": avg_industry_accuracy,
                    "llm_judge_relevance": avg_industry_relevance,
                    "llm_judge_completeness": avg_industry_completeness,
                    "evaluated_cases_count": count
                }
            
            # Log results dictionary as artifact
            try:
                results_path = "rag_model/rag_evaluation_results.json"
                with open(results_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=4)
                mlflow.log_artifact(results_path)
                print(f"Stratified evaluation results saved and logged to MLflow: {results_path}")
            except Exception as e:
                warnings.warn(f"Failed to log evaluation results as MLflow artifact: {e}")


        return results

    def _llm_judge_answer_relevance(self, response: str, ground_truth: str) -> float:
        """Judge how relevant the answer is to the implied question (using ground_truth to infer)."""
        # This prompt assumes the ground truth helps define the question's scope.
        prompt = f"""
            Evaluate the relevance of the 'Generated Answer' to the core question or topic implied by the 'Ground Truth Answer'.
            Score on a scale of 0.0 to 1.0, where 0.0 means completely irrelevant and 1.0 means perfectly relevant to the implied subject.

            Ground Truth Answer (provides context for the implied question):
            {ground_truth}

            Generated Answer:
            {response}

            Return only a single floating-point number between 0.0 and 1.0.
            Examples: 0.0, 0.25, 0.5, 0.75, 1.0
        """
        try:
            judge_response = self.client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            score_str = judge_response.choices[0].message.content.strip()
            import re
            match = re.search(r"(\d\.?\d*)", score_str)
            if match:
                score = float(match.group(1))
                return min(max(score, 0.0), 1.0)
            else:
                 warnings.warn(f"LLM Judge (Relevance) failed to return a parseable number. Response: '{score_str}'. Defaulting to 0.5.")
                 return 0.5
        except Exception as e:
            warnings.warn(f"LLM Judge (Relevance) API call failed: {e}. Defaulting to 0.5.")
            return 0.5


    def _llm_judge_answer_completeness(self, response: str, ground_truth: str) -> float:
        """Judge how complete the answer is compared to the ground truth."""
        prompt = f"""
            Evaluate how completely the 'Generated Answer' covers the key information present in the 'Ground Truth Answer'.
            Score on a scale of 0.0 to 1.0, where 0.0 means it misses almost all key information, and 1.0 means it includes all essential information from the ground truth.

            Ground Truth Answer:
            {ground_truth}

            Generated Answer:
            {response}

            Return only a single floating-point number between 0.0 and 1.0.
            Examples: 0.0, 0.25, 0.5, 0.75, 1.0
        """
        try:
            judge_response = self.client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            score_str = judge_response.choices[0].message.content.strip()
            import re
            match = re.search(r"(\d\.?\d*)", score_str)
            if match:
                score = float(match.group(1))
                return min(max(score, 0.0), 1.0)
            else:
                 warnings.warn(f"LLM Judge (Completeness) failed to return a parseable number. Response: '{score_str}'. Defaulting to 0.5.")
                 return 0.5
        except Exception as e:
            warnings.warn(f"LLM Judge (Completeness) API call failed: {e}. Defaulting to 0.5.")
            return 0.5

    def run_full_evaluation(self, experiment_name: str) -> Dict[str, Any]:
        """
        Run all evaluations (embedding, top-k, full RAG) and log results
        to MLflow, including stratified metrics for bias analysis.

        Args:
            experiment_name: The name for the MLflow experiment.

        Returns:
            A dictionary containing the results from all evaluation steps.
        """
        try:
            mlflow.set_experiment(experiment_name)
        except Exception as e:
            warnings.warn(f"Could not set MLflow experiment '{experiment_name}': {e}. Check MLflow setup.")
            # Decide if you want to proceed without MLflow or raise error
            # For now, we proceed but MLflow logging might fail silently later if setup is wrong.

        all_results = {}

        # Use a single parent run for the entire evaluation process
        with mlflow.start_run(run_name="full_rag_pipeline_evaluation"):
            print("Starting full RAG pipeline evaluation...")

            # Log RAG configuration parameters
            try:
                 mlflow.log_params({
                    "embedding_model": getattr(self.rag_pipeline.config, 'embedding_model', 'N/A'),
                    "llm_model": getattr(self.rag_pipeline.config, 'llm_model', 'N/A'),
                    "configured_top_k": getattr(self.rag_pipeline.config, 'top_k', 'N/A'),
                    "llm_temperature": getattr(self.rag_pipeline.config, 'temperature', 'N/A')
                 })
            except AttributeError:
                 warnings.warn("Could not log all RAG pipeline config parameters. Ensure rag_pipeline.config has expected attributes.")
            except Exception as e:
                 warnings.warn(f"MLflow log_params failed: {e}")


            # --- Evaluate Embedding Model ---
            print("\nEvaluating embedding model (Retrieval Metrics)...")
            try:
                embedding_results = self.evaluate_embedding_model()
                all_results["embedding_evaluation"] = embedding_results
                print("  Embedding evaluation complete.")
                # Log overall embedding metrics
                if "overall" in embedding_results:
                    for metric, value in embedding_results["overall"].items():
                        if isinstance(value, (int, float)): # Log only numeric metrics
                            mlflow.log_metric(f"embedding_{metric}_overall", value)
                # Log stratified embedding metrics (optional, can make MLflow UI busy)
                # Consider logging these as artifacts instead if too numerous
                # Example: log_stratified_metrics_to_mlflow(embedding_results, "embedding")

            except Exception as e:
                print(f"Error during embedding evaluation: {e}")
                all_results["embedding_evaluation"] = {"error": str(e)}

            # --- Evaluate Top-K Strategies ---
            print("\nEvaluating top-k strategies (Answer Accuracy)...")
            try:
                # Define which k values to test
                k_values_to_test = [1, 3, 5] # Example values
                top_k_results = self.evaluate_top_k_strategy(k_values=k_values_to_test)
                all_results["top_k_evaluation"] = top_k_results
                print(f"  Top-k evaluation complete for k={k_values_to_test}.")
                # MLflow logging happens *inside* evaluate_top_k_strategy
            except Exception as e:
                print(f"Error during top-k evaluation: {e}")
                all_results["top_k_evaluation"] = {"error": str(e)}

            # --- Evaluate Full RAG System ---
            print("\nEvaluating full RAG system (BLEU, LLM Judged Metrics)...")
            try:
                rag_results = self.evaluate_rag_system()
                all_results["rag_system_evaluation"] = rag_results
                print("  Full RAG system evaluation complete.")
                # MLflow logging happens *inside* evaluate_rag_system
            except Exception as e:
                print(f"Error during full RAG system evaluation: {e}")
                all_results["rag_system_evaluation"] = {"error": str(e)}

            # --- Log aggregated results as artifact ---
            try:
                all_results_path = "rag_model/full_evaluation_summary.json"
                with open(all_results_path, 'w', encoding='utf-8') as f:
                    # Use default=str to handle potential non-serializable types like defaultdict
                    json.dump(all_results, f, indent=4, default=str)
                mlflow.log_artifact(all_results_path)
                print(f"\nFull evaluation summary saved and logged to MLflow: {all_results_path}")
            except Exception as e:
                warnings.warn(f"Failed to log full evaluation summary artifact: {e}")

            print("\nFull evaluation finished.")
            return all_results