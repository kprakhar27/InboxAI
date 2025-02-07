#!/bin/bash
conf_path="/etc/nginx/sites-available/$1"
available_path="/etc/nginx/sites-enabled/$1"
home_path=$(pwd)/backend

if [ -f "$conf_path" ]
then
    echo "NGINX Configuration file already exists, renewing file..."

    rm "$available_path"
    rm "$conf_path"
else
    echo "NGINX Configuration file doesn't exist, creating file..."
fi

conf_text="server {
    server_name  backend.inboxai.tech;
    server_tokens off;
    root         $home_path;

    # Load configuration files for the default server block.
    include /etc/nginx/default.d/*.conf;

    location / {
        include uwsgi_params;
        uwsgi_pass unix:$home_path/$2;
    }

    error_page 404 /404.html;
        location = /40x.html {
    }

    error_page 500 502 503 504 /50x.html;
        location = /50x.html {
    }


    listen [::]:443 ssl ipv6only=on; # managed by Certbot
    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/backend.inboxai.tech/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/backend.inboxai.tech/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

}
server {
    if ($host = backend.inboxai.tech) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen       80;
    listen       [::]:80;
    server_name  backend.inboxai.tech;
    return 404; # managed by Certbot


}"

echo "$conf_text" > "$conf_path"

chcon unconfined_u:object_r:httpd_config_t:s0 "$conf_path"
chown root:root "$conf_path"

ln -s "$conf_path" "$available_path"

nginx -t
systemctl reload nginx
