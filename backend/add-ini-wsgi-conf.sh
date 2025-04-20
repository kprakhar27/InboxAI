#!/bin/bash
home_path=$(pwd)/backend
wsgi_path="$home_path/wsgi.py"

if [ -f "$wsgi_path" ]; then
    echo "WSGI file already exists, renewing file..."
    rm "$wsgi_path"
else
    echo "WSGI file doesn't exist, creating file..."
fi

wsgi_text="from app import create_app

app = create_app()

if __name__ == \"__main__\":
    app.run()"

echo "$wsgi_text" > "$wsgi_path"
