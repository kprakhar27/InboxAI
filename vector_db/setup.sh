home_vector_path=$(pwd)/vector_db
vector_path=/home/ubuntu/vector-database

if [ -f $vector_path/docker-compose.yaml ]
then
    echo "yes"
    docker-compose -f $vector_path/docker-compose.yaml down
    rm -rf $vector_path
    mkdir $vector_path
    cp -r $home_vector_path/* $vector_path
else
    echo "no"
    mkdir -p $vector_path
    cp -r $home_vector_path/* $vector_path
fi

docker-compose -f $vector_path/docker-compose.yaml up --build -d