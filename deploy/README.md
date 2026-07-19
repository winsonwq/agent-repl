# Sandbox deployment

Build the image:

```bash
docker build -f deploy/Dockerfile -t agent-repl:0.2 .
```

Run one container per Agent task. The host must enforce the security boundary:

```bash
docker run --rm \
  --network none \
  --memory 2g \
  --cpus 2 \
  --pids-limit 64 \
  --read-only \
  --tmpfs /run/agent-repl:rw,noexec,nosuid,size=128m,uid=10001,gid=10001,mode=0700 \
  --tmpfs /tmp:rw,noexec,nosuid,size=512m,uid=10001,gid=10001 \
  --mount type=bind,src=/host/task,dst=/workspace,rw \
  agent-repl:0.2 agent-repl doctor --json
```

For stricter input protection, mount the source material separately at `/workspace/inputs` as read-only and keep `/workspace/working` and `/workspace/outputs` writable volumes. The Kernel is arbitrary Python; container/OS controls, not the Python SDK, enforce file and network isolation.
