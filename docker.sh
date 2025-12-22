# 基础镜像没有变化，不需要每次重新构建
# docker build -t ghcr.io/estom/hexo-blog:base-v1.0.0 -f Dockerfile-base .
# docker push ghcr.io/estom/hexo-blog:base-v1.0.0
docker build -t ghcr.io/estom/hexo-blog:build-v1.0.0 -f Dockerfile-build .
docker push ghcr.io/estom/hexo-blog:build-v1.0.0
docker build -t ghcr.io/estom/hexo-blog:run-v1.0.0 -f Dockerfile-runtime .
docker push ghcr.io/estom/hexo-blog:run-v1.0.0

# 运行基础镜像
docker run -d --name notes -p 80:80 ghcr.io/estom/hexo-blog:run-v1.0.0

# 本地启动hexo 服务器。不适用docker打包的方式
# nohup hexo server -p 4001 &