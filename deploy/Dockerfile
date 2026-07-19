FROM python:3.11-slim

ARG AGENT_REPL_VERSION=0.2.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-calc tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 agent

WORKDIR /opt/agent-repl
COPY . /opt/agent-repl
RUN python -m pip install --no-cache-dir ".[all]" \
    && install -d -o agent -g agent -m 0700 /run/agent-repl /workspace

ENV AGENT_REPL_STATE_DIR=/run/agent-repl \
    AGENT_REPL_SANDBOX_ENFORCED=1 \
    AGENT_REPL_MAX_MEMORY_MB=2048 \
    AGENT_REPL_MAX_CPU_SECONDS=1800 \
    AGENT_REPL_MAX_FILE_MB=1024 \
    AGENT_REPL_MAX_OPEN_FILES=512 \
    AGENT_REPL_MAX_PROCESSES=64 \
    AGENT_REPL_OUTPUT=json \
    HOME=/tmp/agent-home

USER agent
WORKDIR /workspace
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["agent-repl", "doctor", "--json"]
