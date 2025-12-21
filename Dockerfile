# syntax=docker/dockerfile:1

# Build stage uses the prebuilt base image:
#   - Node.js 22
#   - Python 3.12
#   - uv
# Build it locally from Dockerfile-base:
#   docker build -f Dockerfile-base -t hexo-blog:base-node22-py312 .
FROM ghcr.io/Estom/hexo-blog:base-node22-py312 AS build

WORKDIR /app

COPY . .

RUN bash ./build.sh


FROM nginx:1.27-alpine AS runtime

# Static site output from Hexo
COPY --from=build /app/public/ /usr/share/nginx/html/

# Required by user request: runtime starts via start.sh
COPY --from=build /app/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 80
CMD ["/start.sh"]
