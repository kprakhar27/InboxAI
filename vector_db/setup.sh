home_vector_path=$(pwd)/vector_db
vector_path=/home/ubuntu/vector-database

if [ -f $HOME/vector-database/docker-compose.yml ]
then
    echo "yes"
    docker-compose -f $HOME/vector-database/docker-compose.yml down
    rm -rf $HOME/vector-database/docker-compose.yml
    cp -r vector_db/docker-compose.yml $HOME/vector-database/docker-compose.yml
else
    echo "no"
    mkdir -p $HOME/vector-database
    cp -r vector_db/docker-compose.yml $HOME/vector-database/docker-compose.yml
fi