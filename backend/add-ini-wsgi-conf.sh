#!/bin/bash
home_path=$(pwd)/backend
wsgi_path="$home_path/wsgi.py"
ini_path="$home_path/$1"

if [ -f "$ini_path" ]
then
    echo "INI and WSGI files already exists, renewing files..."
    
    rm "$wsgi_path"
    rm "$ini_path"
else
    echo "INI and WSGI files doesn't exist, creating files..."
fi

ini_text="[uwsgi]
module = wsgi:app

master = true
processes = 5

socket = $2
chmod-socket = 660
vacuum = true"

echo "$ini_text" > "$ini_path"

wsgi_text="from app import app

if __name__ == \"__main__\":
    app.run()"

echo "$wsgi_text" > "$wsgi_path"
