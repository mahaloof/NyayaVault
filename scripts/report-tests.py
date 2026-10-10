from pathlib import Path
import json,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
suite=ET.parse(root/'docs/test-results.xml').getroot()
rows=[]
for case in suite.iter('testcase'):
    status='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIPPED' if case.find('skipped') is not None else 'PASS'
    rows.append(f"| {case.attrib['name']} | Automated assertions in backend/tests/test_workflow.py | All assertions succeed | {status} | {float(case.attrib.get('time',0))*1000:.3f} ms |")
a=json.loads((root/'docs/acceptance-results.json').read_text())
text='''# Phase-II executed test report

Generated from actual pytest JUnit results; statuses are not hardcoded.

The backend tests use a fresh SQLite database, the actual Alembic migration, real Argon2 passwords, AES-GCM encryption and encrypted filesystem bytes. Synthetic TXT evidence is used. Results do not establish PostgreSQL, MinIO or live Fabric compatibility.

| Test case | Input / scenario | Expected | Actual | Execution time |
|---|---|---|---|---|
'''+ '\n'.join(rows)
text+='\n\n## Measured acceptance timings\n\nOne automated acceptance execution with a 287-byte synthetic report. Warm local process; these measurements are not a load benchmark. Upload time includes backend processing, not browser transfer.\n\n'
for key,value in a['upload_timings'].items(): text+=f'- {key}: {value:.6f} ms\n'
text+=f"- Original candidate verification: {a['original']['elapsed_ms']:.6f} ms\n- Modified candidate verification: {a['modified']['elapsed_ms']:.6f} ms\n"
text+=f'\n## Scope and current deployment\n\nThese {len(rows)} tests cover a fresh SQLite/local-storage environment and simulated Fabric failure paths. They are separate from the real Docker integration checks. For the current two-organization Fabric, PostgreSQL, MinIO, browser, permission, cleanup, and limitation results, read [FULL_PROJECT_REPORT.md](FULL_PROJECT_REPORT.md). The older standalone Playwright launch failure is historical and is not counted as a pass.\n'
(root/'docs/TEST_REPORT.md').write_text(text)
print(f'Generated report for {len(rows)} executed backend test cases.')
