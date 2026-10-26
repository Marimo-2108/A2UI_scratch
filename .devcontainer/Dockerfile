FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

COPY --chmod=644 cloudflare-root.crt /usr/local/share/ca-certificates/cloudflare.crt
RUN update-ca-certificates