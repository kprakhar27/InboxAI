home_mlflow_path=$(pwd)/mlflow
mlflow_path=/home/ubuntu/mlflow

if [ -f $mlflow_path/docker-compose.yaml ]
then
    echo "yes"
    docker-compose -f $mlflow_path/docker-compose.yml down
    rm -rf $mlflow_path
    mkdir $mlflow_path
    cp -r $home_mlflow_path/* $mlflow_path
else
    echo "no"
    mkdir -p $mlflow_path
    cp -r $home_mlflow_path/* $mlflow_path
    ls -l $mlflow_path
fi

docker-compose -f $mlflow_path/docker-compose.yml up --build -d