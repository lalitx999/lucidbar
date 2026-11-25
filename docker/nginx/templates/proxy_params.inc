# Shared proxy settings (included, not rendered: only *.template files are).
proxy_pass http://lucid_web;
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_set_header Host $host;
# Django reads X-Real-IP for rate limits (TRUST_X_REAL_IP=True in production).
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_read_timeout 60s;
proxy_redirect off;
