#!/usr/bin/env sh
set -eu

# Serve the generated static site (public/) via nginx.
# nginx image already has a default config that serves /usr/share/nginx/html on port 80.
# hexo server # 简单本地服务
exec nginx -g 'daemon off;'
