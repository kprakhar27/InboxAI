FROM apache/airflow:2.10.2

USER root
RUN apt-get update && \
    apt-get install -y wget vim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt

USER root
# Create directories
RUN mkdir -p /opt/airflow/config /opt/airflow/runs

USER airflow