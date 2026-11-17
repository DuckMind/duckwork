FROM node:24-trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git python3 python3-venv python-is-python3 \
    ripgrep procps build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash duckwork \
    && mkdir -p /workspace /home/duckwork/.duckwork \
    && chown -R duckwork:duckwork /workspace /home/duckwork
COPY duckwork-exec.py /usr/local/bin/duckwork-exec
RUN chmod 0755 /usr/local/bin/duckwork-exec
ENV HOME=/home/duckwork
USER duckwork
WORKDIR /workspace
CMD ["sleep", "infinity"]
