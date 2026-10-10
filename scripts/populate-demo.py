#!/usr/bin/env python3
"""Import the fictional demo through the real API, then archive allowlisted tests.

Run with the project's Python environment. This script never deletes evidence,
rewrites history, resets Fabric, or manufactures blockchain transaction IDs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample-data" / "demo-cases"
REPORT = ROOT / "docs" / "demo-refresh-results.json"
ACCOUNTS = ("admin", "investigatorA", "investigatorB", "forensic", "legal")
CASE_FIELDS = ("case_number", "title", "description", "department", "priority", "status")


class DemoImporter:
    def __init__(self, api: str, password: str):
        self.api = api.rstrip("/")
        self.password = password
        self.checks: list[dict] = []
        self.headers: dict[str, dict] = {}
        self.users: dict[str, dict] = {}
        self.new_cases: list[dict] = []
        self.new_evidence: list[dict] = []
        self.backup_path: Path | None = None
        self.started = time.perf_counter()
        self.client = httpx.Client(base_url=self.api, timeout=90)
        self.manifest = json.loads((SAMPLES / "manifest.json").read_text())
        self.originals: dict[str, bytes] = {}

    def check(self, name: str, condition: bool):
        self.checks.append({"test": name, "passed": bool(condition)})
        if not condition:
            raise RuntimeError(name)

    def request(self, method: str, route: str, actor: str = "admin", **kwargs):
        response = self.client.request(method, route, headers=self.headers[actor], **kwargs)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"{method} {route}: HTTP {response.status_code}: {response.text[:500]}")
        return response.json()

    def cases(self, archived: bool = True):
        return self.request("GET", "/cases", params={"include_archived": archived})

    def evidence(self, archived: bool = True):
        return self.request("GET", "/evidence", params={"include_archived": archived})

    def custody(self, evidence: dict):
        history = self.request("GET", f"/evidence/{evidence['id']}/custody")
        label = evidence["evidence_id"]
        self.check(f"{label}: valid custody hash chain", history["ledger"]["valid"])
        self.check(f"{label}: custody upload exists", bool(history["events"]))
        self.check(
            f"{label}: every custody event has a committed Fabric transaction",
            all(
                (event.get("blockchain") or {}).get("status") == "COMMITTED"
                and re.fullmatch(r"[a-f0-9]{64}", (event.get("blockchain") or {}).get("tx_id") or "")
                for event in history["events"]
            ),
        )
        return history

    def validate_manifest(self):
        cases = self.manifest["cases"]
        items = [item for case in cases for item in case["evidence"]]
        self.check("Manifest contains four distinct fictional cases", len(cases) == 4 and len({case["case_number"] for case in cases}) == 4)
        self.check("Manifest contains twelve distinct evidence labels", len(items) == 12 and len({item["evidence_id"] for item in items}) == 12)
        for case in cases:
            self.check(f"{case['case_number']}: known demo lead", case["lead"] in ACCOUNTS)
            for item in case["evidence"]:
                source = (SAMPLES / item["filename"]).resolve()
                self.check(f"{item['evidence_id']}: sample remains inside demo directory", source.parent == SAMPLES.resolve())
                data = source.read_bytes()
                data.decode("utf-8")
                self.check(f"{item['evidence_id']}: nonempty fictional sample", bool(data) and b"fictional" in data.lower())
                self.check(f"{item['evidence_id']}: supported transfer target", item["transfer_to"] in (None, "forensic"))
                datetime.fromisoformat(item["collected_at"])
                self.originals[item["evidence_id"]] = data
        mismatch_items = [item for item in items if item["mismatch"]]
        self.check("Exactly one camera transcript mismatch is requested", len(mismatch_items) == 1 and mismatch_items[0]["evidence_id"] == "NV-0217-CAMERA")
        camera = self.originals["NV-0217-CAMERA"]
        self.check("Camera transcript contains the one intended altered timestamp", camera.count(b"22:18:04") == 1)
        self.check("Exactly one witness note remains unverified", sum(not item["verify"] for item in items) == 1)

    def login(self):
        for account in ACCOUNTS:
            response = self.client.post("/auth/login", json={"email": account.lower() + "@nyayavault.local", "password": self.password})
            self.check(f"Login succeeds for {account}", response.status_code == 200)
            self.headers[account] = {"Authorization": "Bearer " + response.json()["access_token"]}
        users = self.request("GET", "/users")
        for account in ACCOUNTS:
            matches = [user for user in users if user["email"] == account.lower() + "@nyayavault.local"]
            self.check(f"Demo account exists uniquely: {account}", len(matches) == 1)
            self.users[account] = matches[0]
        status = self.request("GET", "/blockchain/status")
        self.check("Real Fabric is connected before import", status["provider"] == "fabric" and status["connected"] is True)
        return status

    def preflight(self):
        cases = self.cases()
        evidence = self.evidence()
        target_numbers = {case["case_number"] for case in self.manifest["cases"]}
        retire_numbers = set(self.manifest["retire_case_numbers"])
        retire_labels = set(self.manifest["retire_evidence_ids"])
        target_labels = set(self.originals)
        self.check("All active cases are demo targets or explicit retirement targets", all(case["status"] == "ARCHIVED" or case["case_number"] in target_numbers | retire_numbers for case in cases))
        active_case_ids = {case["id"] for case in cases if case["status"] != "ARCHIVED"}
        self.check("All active evidence is explicitly accounted for", all(item["case_id"] not in active_case_ids or item["evidence_id"] in target_labels | retire_labels for item in evidence))
        for case in cases:
            if case["case_number"] in retire_numbers:
                labels = {item["evidence_id"] for item in evidence if item["case_id"] == case["id"]}
                self.check(f"{case['case_number']}: retirement includes only allowlisted test evidence", labels <= retire_labels)
        # Validate every existing target before creating anything. A reused label
        # must never silently attach this sample to another case or fingerprint.
        by_number = {case["case_number"]: case for case in cases}
        by_label = {item["evidence_id"]: item for item in evidence}
        for spec in self.manifest["cases"]:
            existing_case = by_number.get(spec["case_number"])
            if existing_case:
                self.check(f"{spec['case_number']}: existing case title matches", existing_case["title"] == spec["title"])
                self.check(f"{spec['case_number']}: existing case metadata matches", all(existing_case[key] == spec[key] for key in CASE_FIELDS))
            for item in spec["evidence"]:
                existing = by_label.get(item["evidence_id"])
                if existing:
                    self.check(f"{item['evidence_id']}: existing case binding matches", existing_case is not None and existing["case_id"] == existing_case["id"])
                    self.validate_existing_evidence(existing, item)
        histories = {item["id"]: self.custody(item) for item in evidence}
        details = {case["id"]: self.request("GET", f"/cases/{case['id']}") for case in cases}
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        folder = ROOT / "blockchain" / "runtime" / "demo-refresh-backups" / stamp
        folder.mkdir(parents=True, mode=0o700)
        folder.chmod(0o700)
        self.backup_path = folder / "baseline.json"
        baseline = {"captured_at": datetime.now(timezone.utc).isoformat(), "cases": cases, "case_details": details, "evidence": evidence, "custody": histories, "users": list(self.users.values())}
        # Exclusive creation avoids accidentally overwriting a prior recovery copy.
        with self.backup_path.open("x") as handle:
            json.dump(baseline, handle, indent=2)
        self.backup_path.chmod(0o600)
        self.check("Private pre-change JSON baseline saved", self.backup_path.is_file())
        return baseline

    def validate_existing_evidence(self, existing: dict, item: dict):
        label = item["evidence_id"]
        self.check(f"{label}: stored original SHA-256 matches sample", existing["sha256_hash"] == hashlib.sha256(self.originals[label]).hexdigest())
        for key, value in (("original_filename", item["filename"]), ("file_size", len(self.originals[label])), ("evidence_type", item["evidence_type"]), ("description", item["description"]), ("source", item["source"]), ("collection_location", item["collection_location"]), ("collected_at", item["collected_at"])):
            self.check(f"{label}: {key} matches manifest", existing[key] == value)

    def ensure_case(self, spec: dict):
        case = next((case for case in self.cases() if case["case_number"] == spec["case_number"]), None)
        required = {user["id"] for user in self.users.values()}
        if case is None:
            case = self.request("POST", "/cases", json={**{key: spec[key] for key in CASE_FIELDS}, "member_ids": sorted(required)})
        detail = self.request("GET", f"/cases/{case['id']}")
        members = {user["id"] for user in detail["members"]}
        if not required <= members:
            self.request("PUT", f"/cases/{case['id']}", json={**{key: detail[key] for key in CASE_FIELDS}, "member_ids": sorted(members | required)})
            detail = self.request("GET", f"/cases/{case['id']}")
        self.check(f"{case['case_number']}: all demo accounts are assigned", required <= {user["id"] for user in detail["members"]})
        self.new_cases.append({"id": case["id"], **{key: spec[key] for key in CASE_FIELDS}})
        return case

    def ensure_evidence(self, case: dict, spec: dict, item: dict):
        label = item["evidence_id"]
        actor = spec["lead"]
        data = self.originals[label]
        trusted = hashlib.sha256(data).hexdigest()
        evidence = next((entry for entry in self.evidence() if entry["evidence_id"] == label), None)
        if evidence is None:
            evidence = self.request("POST", "/evidence", actor, data={"case_id": case["id"], **{key: item[key] for key in ("evidence_id", "evidence_type", "description", "source", "collection_location", "collected_at")}, "tags": "fictional-demo, training"}, files={"file": (item["filename"], data, "text/plain")})
        self.check(f"{label}: correct case binding", evidence["case_id"] == case["id"])
        self.validate_existing_evidence(evidence, item)
        history = self.custody(evidence)
        self.check(f"{label}: upload was committed", any(event["event_type"] == "EVIDENCE_UPLOADED" for event in history["events"]))
        stored_verified = any(event["event_type"] == "INTEGRITY_VERIFIED" and event["metadata_json"].get("candidate") == "stored original" and event["metadata_json"].get("calculated_hash") == trusted for event in history["events"])
        if item["verify"] and not stored_verified:
            result = self.request("POST", f"/evidence/{evidence['id']}/verify", actor)
            self.check(f"{label}: decrypted stored original verifies", result["matched"] and result["trusted_hash"] == trusted and result["calculated_hash"] == trusted)
            history = self.custody(evidence)
        elif not item["verify"]:
            self.check(f"{label}: witness note has no verification event", not any(event["event_type"] in ("INTEGRITY_VERIFIED", "INTEGRITY_FAILED") for event in history["events"]))
        if item["transfer_to"]:
            recipient = self.users[item["transfer_to"]]["id"]
            transfer_done = any(event["event_type"] == "CUSTODY_TRANSFERRED" and event["to_custodian_id"] == recipient for event in history["events"])
            if not transfer_done:
                self.check(f"{label}: custody is still held by the uploading lead", evidence["current_custodian_id"] == self.users[actor]["id"])
                evidence = self.request("POST", f"/evidence/{evidence['id']}/transfer", actor, json={"to_custodian_id": recipient, "reason": "Fictional demonstration: sealed digital evidence handed to the forensic officer for examination."})
                history = self.custody(evidence)
            self.check(f"{label}: forensic custody is current", evidence["current_custodian_id"] == recipient)
        else:
            self.check(f"{label}: no unsolicited custody transfer", not any(event["event_type"] == "CUSTODY_TRANSFERRED" for event in history["events"]))
        if item["mismatch"]:
            candidate = data.replace(b"22:18:04", b"22:19:04", 1)
            candidate_hash = hashlib.sha256(candidate).hexdigest()
            mismatch_done = any(event["event_type"] == "INTEGRITY_FAILED" and event["metadata_json"].get("calculated_hash") == candidate_hash for event in history["events"])
            if not mismatch_done:
                verifier = item["transfer_to"] or actor
                result = self.request("POST", f"/evidence/{evidence['id']}/verify", verifier, files={"file": ("junction_camera_observation_modified_demo.txt", candidate, "text/plain")})
                self.check(f"{label}: deliberately changed camera timestamp is detected", not result["matched"] and result["trusted_hash"] == trusted and result["calculated_hash"] == candidate_hash)
                history = self.custody(evidence)
        final = next(entry for entry in self.evidence() if entry["id"] == evidence["id"])
        expected_integrity = "INTEGRITY_ALERT" if item["mismatch"] else "VERIFIED" if item["verify"] else "UNVERIFIED"
        self.check(f"{label}: final integrity state is {expected_integrity}", final["integrity_status"] == expected_integrity)
        self.check(f"{label}: immutable original fingerprint preserved", final["sha256_hash"] == trusted)
        self.new_evidence.append({"id": final["id"], "evidence_id": label, "case_number": case["case_number"], "sha256_hash": trusted, "integrity_status": final["integrity_status"], "custody_events": len(history["events"]), "transactions": [{"event_id": event["id"], "event_type": event["event_type"], "timestamp": event["timestamp"], "tx_id": event["blockchain"]["tx_id"]} for event in history["events"]]})

    def archive_tests(self, baseline: dict):
        # No retirement happens until all twelve registrations and requested
        # workflow events have passed the real commit checks above.
        self.check("All twelve demo items are ready before retirement", len(self.new_evidence) == 12)
        retire_numbers = set(self.manifest["retire_case_numbers"])
        retire_labels = set(self.manifest["retire_evidence_ids"])
        cases = self.cases()
        evidence = self.evidence()
        targets = [case for case in cases if case["case_number"] in retire_numbers]
        # Validate the whole allowlist again before the first archive mutation.
        for case in targets:
            labels = {item["evidence_id"] for item in evidence if item["case_id"] == case["id"]}
            self.check(f"{case['case_number']}: retirement allowlist rechecked", labels <= retire_labels)
            for item in evidence:
                if item["case_id"] == case["id"]:
                    before = baseline["custody"].get(item["id"])
                    self.check(f"{item['evidence_id']}: original custody history unchanged before archive", before is not None and self.custody(item) == before)
        archived = []
        for case in targets:
            detail = self.request("GET", f"/cases/{case['id']}")
            member_ids = {user["id"] for user in detail["members"]}
            if case["status"] != "ARCHIVED":
                payload = {key: detail[key] for key in CASE_FIELDS}
                payload.update(status="ARCHIVED", member_ids=sorted(member_ids))
                self.request("PUT", f"/cases/{case['id']}", json=payload)
            after = self.request("GET", f"/cases/{case['id']}")
            self.check(f"{case['case_number']}: case is archived", after["status"] == "ARCHIVED")
            self.check(f"{case['case_number']}: original memberships preserved", {user["id"] for user in after["members"]} == member_ids)
            self.check(f"{case['case_number']}: case content preserved", all(after[key] == detail[key] for key in CASE_FIELDS if key != "status"))
            archived.append(case["case_number"])
        after_evidence = {item["id"]: item for item in self.evidence()}
        for item in baseline["evidence"]:
            if item["evidence_id"] in retire_labels:
                self.check(f"{item['evidence_id']}: encrypted evidence metadata and transaction references preserved", after_evidence.get(item["id"]) == item)
                self.check(f"{item['evidence_id']}: complete original custody history preserved after archive", self.custody(item) == baseline["custody"][item["id"]])
        return archived

    def final_checks(self):
        cases = self.cases(archived=False)
        evidence = self.evidence(archived=False)
        expected_cases = {case["case_number"] for case in self.manifest["cases"]}
        expected_evidence = set(self.originals)
        self.check("Active case list contains exactly the four realistic demo scenarios", {case["case_number"] for case in cases} == expected_cases and len(cases) == 4)
        self.check("Active evidence list contains exactly twelve fictional demo originals", {item["evidence_id"] for item in evidence} == expected_evidence and len(evidence) == 12)
        for account in ACCOUNTS:
            visible_cases = self.request("GET", "/cases", account)
            visible_evidence = self.request("GET", "/evidence", account)
            self.check(f"{account}: assigned four cases and twelve evidence items are visible", {case["case_number"] for case in visible_cases} == expected_cases and {item["evidence_id"] for item in visible_evidence} == expected_evidence)
        dashboard = self.request("GET", "/dashboard")
        self.check("Dashboard shows four cases and twelve evidence items", dashboard["total_cases"] == 4 and dashboard["total_evidence"] == 12)
        self.check("Dashboard shows ten verified originals and one deliberate alert", dashboard["verified"] == 10 and dashboard["alerts"] == 1)
        self.check("One witness note remains honestly unverified", sum(item["integrity_status"] == "UNVERIFIED" for item in evidence) == 1)
        self.check("Dashboard records the seven requested forensic handoffs", dashboard["transfers"] == 7)
        self.check("Dashboard records eleven successful checks and one modified candidate", dashboard["successful_verifications"] == 11 and dashboard["detected_mismatches"] == 1 and dashboard["verification_attempts"] == 12)
        histories = [self.custody(item) for item in evidence]
        count = sum(len(history["events"]) for history in histories)
        self.check("Dashboard committed count equals actual active custody events", dashboard["blockchain_transactions"] == count and dashboard["failed_blockchain_transactions"] == 0)
        self.check("Fabric remains connected after demo refresh", dashboard["blockchain"]["provider"] == "fabric" and dashboard["blockchain"]["connected"] is True)
        return {"active_cases": len(cases), "active_evidence": len(evidence), "all_cases_including_archived": len(self.cases()), "all_evidence_including_archived": len(self.evidence()), "verified": dashboard["verified"], "integrity_alerts": dashboard["alerts"], "unverified": 1, "custody_events": count, "committed_transactions": dashboard["blockchain_transactions"], "forensic_transfers": dashboard["transfers"], "verification_attempts": dashboard["verification_attempts"], "successful_verifications": dashboard["successful_verifications"], "modified_candidates_detected": dashboard["detected_mismatches"]}, dashboard

    def run(self):
        self.validate_manifest()
        initial_status = self.login()
        baseline = self.preflight()
        for spec in self.manifest["cases"]:
            case = self.ensure_case(spec)
            for item in spec["evidence"]:
                self.ensure_evidence(case, spec, item)
        archived = self.archive_tests(baseline)
        counts, dashboard = self.final_checks()
        return {"status": "passed", "fictional": True, "api": self.api, "completed_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": round(time.perf_counter() - self.started, 3), "private_baseline": str(self.backup_path.relative_to(ROOT)), "archive_method": "Case status ARCHIVED; original objects, metadata, memberships, custody events and transaction IDs retained", "archived_case_numbers": archived, "cases": self.new_cases, "evidence": self.new_evidence, "actual_counts": counts, "dashboard": dashboard, "initial_blockchain_status": initial_status, "report_checks": self.checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=os.environ.get("NYAYAVAULT_DEMO_API", "http://127.0.0.1:8001/api"))
    args = parser.parse_args()
    importer = DemoImporter(args.api, os.environ.get("NYAYAVAULT_DEMO_PASSWORD", "DemoOnly!2026"))
    try:
        result = importer.run()
    except Exception as exc:
        result = {"status": "failed", "api": importer.api, "error": str(exc), "elapsed_seconds": round(time.perf_counter() - importer.started, 3), "private_baseline": str(importer.backup_path.relative_to(ROOT)) if importer.backup_path else None, "cases_processed": importer.new_cases, "evidence_processed": importer.new_evidence, "report_checks": importer.checks}
        REPORT.write_text(json.dumps(result, indent=2) + "\n")
        raise
    finally:
        importer.client.close()
    REPORT.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Demo refresh complete: {len(importer.checks)} checks passed; four active cases, twelve active evidence items. Report: docs/{REPORT.name}")


if __name__ == "__main__":
    main()
