FROM apache/airflow:2.10.2
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt
USER root
RUN apt-get update && apt-get install -y wget