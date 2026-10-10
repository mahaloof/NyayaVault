# MinIO image built from official source

The previously configured public binary image could not be pulled from Docker Hub or Quay on 2026-10-05. This image builds the official MinIO source at commit `7aac2a2c5b7c882e68c1ce017d8256be2feea27f` with Go 1.24.8.

Source and license: https://github.com/minio/minio/tree/7aac2a2c5b7c882e68c1ce017d8256be2feea27f (GNU AGPLv3).

The upstream community repository is archived. This is a reproducible academic demonstration dependency, not a claim of ongoing security maintenance or production suitability. No unofficial prebuilt image is used. The binary runs as a non-root user; the evidence bucket holds application-encrypted ciphertext.
