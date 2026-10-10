FROM docker:28-cli AS dockercli
FROM python:3.12-slim
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
RUN pip install --no-cache-dir httpx==0.28.1
WORKDIR /workspace
COPY docker/portable-tools/config.py /opt/nyayavault/config.py
COPY scripts /workspace/scripts
COPY sample-data /workspace/sample-data
RUN mkdir -p /workspace/docs /workspace/blockchain/runtime
CMD ["python", "/opt/nyayavault/config.py", "validate"]
