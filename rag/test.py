import mlflow
from mlflow.tracking import MlflowClient
from mlflow.entities import ViewType
import pandas as pd
from dotenv import load_dotenv
import os


def get_latest_run_for_all_experiments():
    """
    Retrieves the latest run from each experiment in MLflow.
    
    Returns:
        A pandas DataFrame containing experiment name, experiment ID, 
        run ID, status, start time, end time, and metrics for the latest run of each experiment.
    """
    # Initialize MLflow client
    client = MlflowClient()
    
    # Get all experiments
    experiments = client.search_experiments()
    
    # Initialize a list to store the latest run info for each experiment
    latest_runs_data = []
    
    for experiment in experiments:
        experiment_id = experiment.experiment_id
        experiment_name = experiment.name
        
        # Search for runs in this experiment, ordered by start_time desc
        runs = client.search_runs(
            experiment_ids=[experiment_id],
            filter_string="",
            run_view_type=ViewType.ACTIVE_ONLY,
            max_results=1,
            order_by=["start_time DESC"]
        )
        
        # If there are any runs for this experiment
        if runs:
            latest_run = runs[0]
            
            # Extract run information
            run_data = {
                "experiment_name": experiment_name,
                "experiment_id": experiment_id,
                "run_id": latest_run.info.run_id,
                "status": latest_run.info.status,
                "start_time": pd.to_datetime(latest_run.info.start_time, unit='ms'),
                "end_time": pd.to_datetime(latest_run.info.end_time, unit='ms') if latest_run.info.end_time else None,
            }
            
            # Add metrics to the run data
            for key, value in latest_run.data.metrics.items():
                run_data[f"metric_{key}"] = value
            
            # Add parameters to the run data
            for key, value in latest_run.data.params.items():
                run_data[f"param_{key}"] = value
                
            latest_runs_data.append(run_data)
    
    # Convert to DataFrame
    latest_runs_df = pd.DataFrame(latest_runs_data)
    
    return latest_runs_df

def print_latest_run_metrics(latest_runs_df):
    """
    Prints the metrics for each latest run in a readable format.
    
    Args:
        latest_runs_df: DataFrame containing the latest runs data
    """
    if latest_runs_df.empty:
        print("No runs found in any experiments.")
        return
    
    print(f"Found latest runs for {len(latest_runs_df)} experiments:\n")
    
    for _, row in latest_runs_df.iterrows():
        print(f"Experiment: {row['experiment_name']}")
        print(f"  Run ID: {row['run_id']}")
        print(f"  Status: {row['status']}")
        print(f"  Start Time: {row['start_time']}")
        
        # Print all metrics for this run
        metrics = {k: v for k, v in row.items() if k.startswith('metric_')}
        if metrics:
            print("  Metrics:")
            for metric_name, metric_value in metrics.items():
                # Remove the 'metric_' prefix for cleaner output
                clean_name = metric_name.replace('metric_', '')
                print(f"    {clean_name}: {metric_value}")
        else:
            print("  Metrics: None")
        print("-" * 50)

if __name__ == "__main__":
    # Set the MLflow tracking URI if needed
    # mlflow.set_tracking_uri("http://localhost:5000")
    load_dotenv()
    
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
    
    # Get the latest runs
    latest_runs = get_latest_run_for_all_experiments()
    
    # Display the results
    if not latest_runs.empty:
        print(f"Found latest runs for {len(latest_runs)} experiments:")
        print(latest_runs[["experiment_name", "run_id", "start_time", "status"]])
        print_latest_run_metrics(latest_runs)
    else:
        print("No runs found in any experiments.")