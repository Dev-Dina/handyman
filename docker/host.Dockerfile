FROM nginx:alpine
# Serve the full-featured demo host page from demo/host/.
# The placeholder at host/index.html (project root) is not used here.
COPY demo/host/ /usr/share/nginx/html/
