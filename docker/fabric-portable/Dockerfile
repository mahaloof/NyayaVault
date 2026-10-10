FROM debian:bookworm-slim
ARG FABRIC_VERSION=2.5.16
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl jq openssl tar gzip coreutils util-linux && rm -rf /var/lib/apt/lists/*
RUN test "${TARGETARCH}" = amd64 -o "${TARGETARCH}" = arm64 && mkdir -p /opt/fabric && curl -fSL --retry 5 "https://github.com/hyperledger/fabric/releases/download/v${FABRIC_VERSION}/hyperledger-fabric-linux-${TARGETARCH}-${FABRIC_VERSION}.tar.gz" | tar -xz -C /opt/fabric
ENV PATH="/opt/fabric/bin:${PATH}" FABRIC_CFG_PATH=/opt/fabric/config
COPY docker/fabric-portable /bootstrap
COPY blockchain/chaincode/index.js blockchain/chaincode/package.json blockchain/chaincode/package-lock.json /implementation/
RUN sed -i 's/\r$//' /bootstrap/*.sh /bootstrap/*.yaml && chmod +x /bootstrap/*.sh
ENTRYPOINT ["bash", "/bootstrap/bootstrap.sh"]
CMD ["setup"]
