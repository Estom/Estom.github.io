# syntax=docker/dockerfile:1

# Build stage uses a prebuilt base image:
#   - Node.js 22
#   - Python 3.12
#   - uv
#
ARG BASE_IMAGE=ghcr.io/estom/hexo-blog:base-v1.0.0
FROM ${BASE_IMAGE} AS build

WORKDIR /app

COPY . .

# NOTE_REPO_URL can be baked into the image at build time via --build-arg,
# and can also be overridden at container runtime via -e NOTE_REPO_URL=...
ARG NOTE_REPO_URL=
ENV NOTE_REPO_URL=${NOTE_REPO_URL}

RUN bash ./build.sh


FROM nginx:1.27-alpine AS runtime

# Static site output from Hexo
COPY --from=build /app/public/ /usr/share/nginx/html/

# Required by user request: runtime starts via start.sh
COPY --from=build /app/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 80
CMD ["/start.sh"]
