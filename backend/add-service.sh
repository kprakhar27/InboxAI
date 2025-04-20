#!/bin/bash
# Usage: ./create_systemd_service.sh service_name user venv_folder socket_name
home_path=$(pwd)
service_path="/etc/systemd/system/$1.service"

if [ -f "$service_path" ]; then
    echo "Service file already exists, renewing file..."
    systemctl stop "$1.service"
    systemctl disable "$1.service"
    rm "$service_path"
else
    echo "Service file doesn't exist, creating file..."
fi

socket_path="$home_path/backend/$4"

service_contents="[Unit]
Description=Gunicorn instance to serve Flask Web App
After=network.target

[Service]
User=$2
Group=www-data
WorkingDirectory=$home_path/backend
Environment=\"PATH=$home_path/backend/$3/bin\"
ExecStart=$home_path/backend/$3/bin/gunicorn -b unix:$socket_path wsgi:app

[Install]
WantedBy=multi-user.target"

echo "$service_contents" > "$service_path"

systemctl daemon-reload
systemctl start "$1.service"
systemctl enable "$1.service"
