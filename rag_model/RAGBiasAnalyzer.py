from typing import Any, Dict, List

import mlflow
import numpy as np
import pandas as pd


class RAGBiasAnalyzer:
    """
    Analyzer for detecting potential biases in RAG system responses
    """

    def __init__(self, rag_evaluator):
        """
        Initialize bias analyzer with existing RAG evaluator

        Args:
            rag_evaluator: Instance of RAGEvaluator
        """
        self.rag_evaluator = rag_evaluator
        self.client = rag_evaluator.client

    def analyze_topic_bias(self) -> Dict[str, Any]:
        """
        Analyze potential bias across different topics and industries

        Returns:
            Dictionary of bias analysis results
        """
        # Organize test cases by topic and industry
        topic_results = {}
        industry_results = {}

        # Group test cases
        topic_cases = {}
        industry_cases = {}

        for test_case in self.rag_evaluator.test_dataset:
            topic = test_case.get("topic", "Unknown")
            industry = test_case.get("industry", "Unknown")

            if topic not in topic_cases:
                topic_cases[topic] = []
            topic_cases[topic].append(test_case)

            if industry not in industry_cases:
                industry_cases[industry] = []
            industry_cases[industry].append(test_case)

        # Analyze bias by topic
        with mlflow.start_run(nested=True, run_name="topic_bias_analysis"):
            for topic, cases in topic_cases.items():
                topic_results[topic] = self._analyze_subset_bias(cases, "topic")
                mlflow.log_metrics(
                    {
                        f"{topic}_accuracy": topic_results[topic]["accuracy"],
                        f"{topic}_relevance": topic_results[topic]["relevance"],
                        f"{topic}_completeness": topic_results[topic]["completeness"],
                    }
                )

            # Analyze bias by industry
            for industry, cases in industry_cases.items():
                industry_results[industry] = self._analyze_subset_bias(
                    cases, "industry"
                )
                mlflow.log_metrics(
                    {
                        f"{industry}_accuracy": industry_results[industry]["accuracy"],
                        f"{industry}_relevance": industry_results[industry][
                            "relevance"
                        ],
                        f"{industry}_completeness": industry_results[industry][
                            "completeness"
                        ],
                    }
                )

        # Calculate overall bias metrics
        bias_analysis = {
            "topic_results": topic_results,
            "industry_results": industry_results,
            "bias_indicators": self._calculate_bias_indicators(
                topic_results, industry_results
            ),
        }

        return bias_analysis

    def _analyze_subset_bias(
        self, cases: List[Dict], subset_type: str
    ) -> Dict[str, float]:
        """
        Analyze bias for a subset of test cases

        Args:
            cases: List of test cases for a specific topic/industry
            subset_type: 'topic' or 'industry'

        Returns:
            Dictionary of bias metrics
        """
        predictions = []
        ground_truths = []

        for test_case in cases:
            query = test_case["query"]
            ground_truth = test_case["ground_truth"]

            rag_result = self.rag_evaluator.rag_pipeline.query(query)
            predictions.append(rag_result["response"])
            ground_truths.append(ground_truth)

        # Calculate metrics
        accuracy_sum = 0
        relevance_sum = 0
        completeness_sum = 0

        for pred, truth in zip(predictions, ground_truths):
            accuracy = self.rag_evaluator._llm_judge_answer_quality(pred, truth)
            relevance = self.rag_evaluator._llm_judge_answer_relevance(pred, truth)
            completeness = self.rag_evaluator._llm_judge_answer_completeness(
                pred, truth
            )

            accuracy_sum += accuracy
            relevance_sum += relevance
            completeness_sum += completeness

        num_cases = len(cases)
        return {
            "accuracy": accuracy_sum / num_cases,
            "relevance": relevance_sum / num_cases,
            "completeness": completeness_sum / num_cases,
            "sample_size": num_cases,
        }

    def _calculate_bias_indicators(
        self, topic_results: Dict, industry_results: Dict
    ) -> Dict[str, float]:
        """
        Calculate overall bias indicators

        Args:
            topic_results: Results by topic
            industry_results: Results by industry

        Returns:
            Dictionary of bias indicators
        """

        # Variance analysis to detect potential bias
        def calculate_variance(results):
            accuracies = [r["accuracy"] for r in results.values()]
            relevances = [r["relevance"] for r in results.values()]
            completeness = [r["completeness"] for r in results.values()]

            return {
                "accuracy_variance": np.var(accuracies),
                "relevance_variance": np.var(relevances),
                "completeness_variance": np.var(completeness),
            }

        # Check for significant variations
        topic_variance = calculate_variance(topic_results)
        industry_variance = calculate_variance(industry_results)

        # Bias indicators
        bias_indicators = {
            "topic_accuracy_variance": topic_variance["accuracy_variance"],
            "topic_relevance_variance": topic_variance["relevance_variance"],
            "topic_completeness_variance": topic_variance["completeness_variance"],
            "industry_accuracy_variance": industry_variance["accuracy_variance"],
            "industry_relevance_variance": industry_variance["relevance_variance"],
            "industry_completeness_variance": industry_variance[
                "completeness_variance"
            ],
        }

        return bias_indicators

    def generate_bias_report(
        self, experiment_name: str = "RAG_Bias_Analysis"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive bias analysis report

        Args:
            experiment_name: Name of the MLflow experiment

        Returns:
            Comprehensive bias analysis report
        """
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(run_name="comprehensive_bias_analysis"):
            # Run bias analysis
            bias_analysis = self.analyze_topic_bias()

            # Log overall bias indicators
            bias_indicators = bias_analysis["bias_indicators"]
            for metric, value in bias_indicators.items():
                mlflow.log_metric(metric, value)

            # Create detailed report
            report = {
                "experiment_name": experiment_name,
                "timestamp": pd.Timestamp.now().isoformat(),
                "bias_analysis": bias_analysis,
            }

            return report


# Usage example
# bias_analyzer = RAGBiasAnalyzer(rag_evaluator)
# bias_report = bias_analyzer.generate_bias_report()
