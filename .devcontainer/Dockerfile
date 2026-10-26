FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

COPY --chmod=644 cloudflare-root.crt /usr/local/share/ca-certificates/cloudflare.crt
RUN sudo update-ca-certificates
ENV SHELL=/bin/zsh