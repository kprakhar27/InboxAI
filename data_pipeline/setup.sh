#!/bin/bash
home_path=$(pwd)/data_pipeline
airflow_path=/home/ubuntu/airflow
vector_path=/home/ubuntu/vector-database

if [ -f $airflow_path/docker-compose.yaml ]
then
    echo "yes"
    if [-f $airflow_path/docker-compose.yaml ]
    then
        docker-compose -f $vector_path/docker-compose.yaml down
    fi
    docker-compose -f $airflow_path/docker-compose.yaml down
    rm -rf $airflow_path
    mkdir $airflow_path
    cp -r $home_path/* $airflow_path
else
    echo "no"
    mkdir -p $airflow_path
    cp -r $home_path/* $airflow_path
fi

docker-compose -f $airflow_path/docker-compose.yaml up --build -d
if [ -f $vector_path/docker-compose.yaml ]
then
    docker-compose -f $vector_path/docker-compose.yaml up --build -d
fi
