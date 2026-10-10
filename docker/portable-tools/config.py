#!/usr/bin/env python3
"""Container-only portable configuration and readiness helper. Never prints secrets."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

REQUIRED = (
    "POSTGRES_PASSWORD", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "JWT_SECRET",
    "EVIDENCE_MASTER_KEY", "FABRIC_GATEWAY_SECRET", "FRONTEND_PORT", "BACKEND_PORT",
    "MINIO_CONSOLE_PORT",
)
PORT_DEFAULTS = {"FRONTEND_PORT": 3001, "BACKEND_PORT": 8001, "MINIO_CONSOLE_PORT": 9001}


def read_config(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError("Portable configuration is missing. Run the portable start script first.")
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Portable configuration contains an invalid line.")
        name, value = line.split("=", 1)
        if name in values:
            raise ValueError("Portable configuration contains a duplicate setting.")
        values[name] = value
    if any(not values.get(key) for key in REQUIRED):
        raise ValueError("Portable configuration is incomplete. Restore its original copy; do not replace encryption keys.")
    for key in ("POSTGRES_PASSWORD", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "JWT_SECRET", "FABRIC_GATEWAY_SECRET"):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", values[key]):
            raise ValueError("Portable secrets must use letters, digits, underscores or hyphens.")
    for key in ("POSTGRES_PASSWORD", "MINIO_SECRET_KEY", "JWT_SECRET", "FABRIC_GATEWAY_SECRET"):
        if len(values[key]) < 32:
            raise ValueError("Portable configuration contains a secret shorter than 32 characters.")
    try:
        if len(base64.b64decode(values["EVIDENCE_MASTER_KEY"], validate=True)) != 32:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("EVIDENCE_MASTER_KEY must be the original base64-encoded 32-byte key.") from None
    ports = []
    for key in PORT_DEFAULTS:
        try:
            port = int(values[key])
        except ValueError:
            raise ValueError("Portable configuration has an invalid port.") from None
        if not 1024 <= port <= 65535:
            raise ValueError("Portable ports must be between 1024 and 65535.")
        ports.append(port)
    if len(set(ports)) != len(ports):
        raise ValueError("Frontend, backend and storage-console ports must differ.")
    return values


def ensure(path: Path, ports: dict[str, int]):
    if path.exists():
        read_config(path)
        print("Using existing portable configuration and encryption key.")
        return
    values = {
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "MINIO_ACCESS_KEY": "nv" + secrets.token_hex(10),
        "MINIO_SECRET_KEY": secrets.token_hex(32),
        "JWT_SECRET": secrets.token_hex(32),
        "EVIDENCE_MASTER_KEY": base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
        "FABRIC_GATEWAY_SECRET": secrets.token_hex(32),
        **{key: str(value) for key, value in ports.items()},
    }
    content = (
        "# Private NyayaVault portable configuration. Keep with any backup.\n"
        "# Do not regenerate EVIDENCE_MASTER_KEY for an existing evidence store.\n"
        + "\n".join(f"{key}={values[key]}" for key in REQUIRED) + "\n"
    ).encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".portable-config-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # A hard link publishes the complete file atomically and refuses to
        # overwrite a file created by another start process in the meantime.
        try:
            os.link(temporary, path)
        except FileExistsError:
            read_config(path)
            print("Using existing portable configuration and encryption key.")
            return
        read_config(path)
        print("Created private portable configuration. Keep .env.portable with your backups.")
    finally:
        Path(temporary).unlink(missing_ok=True)


def wait_for(urls: list[str], timeout: int):
    pending = set(urls)
    deadline = time.monotonic() + timeout
    while pending:
        for url in tuple(pending):
            try:
                with urlopen(url, timeout=5) as response:
                    if response.status == 200:
                        pending.remove(url)
            except (HTTPError, URLError, TimeoutError, OSError):
                pass
        if not pending:
            print("Application and web interface are ready.")
            return
        if time.monotonic() >= deadline:
            raise ValueError("Application did not become ready. Inspect portable status and Docker logs; data was retained.")
        time.sleep(3)


def populate_once(api: str):
    """Seed empty or interrupted demo workspaces without changing user cases."""
    import httpx

    marker = Path("/workspace/blockchain/runtime/portable-demo-complete.json")
    if marker.is_file():
        print("Demo initialization is already complete. Existing cases and evidence were retained.")
        return
    api = api.rstrip("/")
    with httpx.Client(base_url=api, timeout=30) as client:
        login = client.post("/auth/login", json={"email": "admin@nyayavault.local", "password": os.environ.get("NYAYAVAULT_DEMO_PASSWORD", "DemoOnly!2026")})
        if login.status_code != 200:
            raise ValueError("Could not inspect the workspace with the demo administrator; run start with --no-demo for existing custom accounts.")
        response = client.get("/cases", params={"include_archived": True}, headers={"Authorization": "Bearer " + login.json()["access_token"]})
        if response.status_code != 200:
            raise ValueError("Could not inspect existing cases before demo initialization.")
        cases = response.json()
    manifest = json.loads(Path("/workspace/sample-data/demo-cases/manifest.json").read_text())
    numbers = {case["case_number"] for case in manifest["cases"]}
    if any(case["case_number"] not in numbers for case in cases):
        print("Existing case records found. Automatic demo import was skipped to preserve this workspace.")
        result = {"demo_imported": False, "reason": "existing case records retained"}
    else:
        completed = subprocess.run([sys.executable, "/workspace/scripts/populate-demo.py", "--api", api], check=False)
        if completed.returncode:
            raise ValueError("Demo initialization stopped before completion. Its real records were retained; restart to resume.")
        result = {"demo_imported": True, "reason": "fictional demo completed through the real API"}
    marker.parent.mkdir(parents=True, exist_ok=True)
    with marker.open("x", encoding="utf-8") as handle:
        json.dump(result, handle)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("ensure", "validate", "urls"):
        command = sub.add_parser(name)
        command.add_argument("--file", type=Path, default=Path("/project/.env.portable"))
        if name == "ensure":
            for key, value in PORT_DEFAULTS.items():
                command.add_argument("--" + key.lower().replace("_", "-"), type=int, default=value)
    wait = sub.add_parser("wait")
    wait.add_argument("--url", action="append", required=True)
    wait.add_argument("--timeout", type=int, default=180)
    demo = sub.add_parser("demo")
    demo.add_argument("--api", default="http://backend:8000/api")
    args = parser.parse_args()
    try:
        if args.action == "ensure":
            ports = {key: getattr(args, key.lower()) for key in PORT_DEFAULTS}
            if any(not 1024 <= value <= 65535 for value in ports.values()) or len(set(ports.values())) != 3:
                raise ValueError("Choose three distinct portable ports between 1024 and 65535.")
            ensure(args.file, ports)
        elif args.action == "validate":
            read_config(args.file)
            print("Portable configuration is valid.")
        elif args.action == "urls":
            config = read_config(args.file)
            print(f"NyayaVault: http://localhost:{config['FRONTEND_PORT']}")
            print(f"API health: http://localhost:{config['BACKEND_PORT']}/api/health")
            print(f"Storage console: http://localhost:{config['MINIO_CONSOLE_PORT']}")
        elif args.action == "wait":
            wait_for(args.url, args.timeout)
        else:
            populate_once(args.api)
    except (OSError, ValueError) as exc:
        # Errors contain setting names or service hints, never setting values.
        print(f"Portable setup: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
