"""Drive the seeded demo end-to-end over the HTTP API.

Where ``seed_demo.py`` creates the durable resources straight in the database,
this script exercises the *execution* and *metrics* features against a running
server, exactly as the frontend does — so you get real pipeline runs, test-case
verdicts and a transcription metric with genuine latency numbers to show.

Steps (for one demo account):
  1. Log in (POST /auth/login)                    -> Bearer token
  2. Find the "Voice Demo" pipeline               (GET /pipelines/)
  3. Run the pipeline                             (POST /runs/pipelines/{id})
  4. Run each of its test cases                   (POST /test-cases/{pid}/{tid}/runs)
  5. Run a standalone streaming transcription     (POST /transcriptions/)
     with a real time-to-first-token, and validate the transcript.

Prerequisites:
  * The server is running (e.g. `fastapi dev main.py`) and reachable.
  * `seed_demo.py` has been run so the account + pipeline exist.
  * A valid ASSEMBLYAI_API_KEY in .env and outbound network access.
  * Step 5 uses streaming mode, which needs ffmpeg on PATH.

Usage (from the project root)::

    python scripts/run_demo.py
    python scripts/run_demo.py --email user@example.com
    python scripts/run_demo.py --base-url http://127.0.0.1:8000 --skip-transcribe
    python scripts/run_demo.py --max-audio-seconds 20
"""

import argparse
import sys

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_EMAIL = "la.benjamib@gmail.com"
DEFAULT_PASSWORD = "callstack-demo-123"  # nosec - matches seed_demo.py's demo password
DEFAULT_PIPELINE_NAME = "Voice Demo"
SAMPLE_AUDIO_URL = "https://assembly.ai/wildfires.mp3"

# Generous: batch transcription + an LLM call can take a while end to end.
_TIMEOUT = httpx.Timeout(180.0, connect=10.0)


def _fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _login(client: httpx.Client, email: str, password: str) -> str:
    # /auth/login takes OAuth2 form fields (username/password), not JSON.
    resp = client.post("/auth/login", data={"username": email, "password": password})
    if resp.status_code != 200:
        _fail(f"login failed for {email}: {resp.status_code} {resp.text[:200]}")
    return resp.json()["access_token"]


def _find_pipeline(client: httpx.Client, name: str) -> dict:
    resp = client.get("/pipelines/")
    resp.raise_for_status()
    for pipeline in resp.json()["pipelines"]:
        if pipeline["name"] == name:
            return pipeline
    _fail(f"pipeline {name!r} not found — run scripts/seed_demo.py first")


def _run_pipeline(client: httpx.Client, pipeline_id: str) -> dict:
    resp = client.post(f"/runs/pipelines/{pipeline_id}")
    resp.raise_for_status()
    return resp.json()


def _list_test_cases(client: httpx.Client, pipeline_id: str) -> list[dict]:
    resp = client.get(f"/test-cases/{pipeline_id}/")
    resp.raise_for_status()
    return resp.json()["test_cases"]


def _run_test_case(client: httpx.Client, pipeline_id: str, test_case_id: str) -> dict:
    resp = client.post(f"/test-cases/{pipeline_id}/{test_case_id}/runs")
    resp.raise_for_status()
    return resp.json()


def _transcribe(client: httpx.Client, max_audio_seconds: int) -> dict:
    payload = {
        "audio_url": SAMPLE_AUDIO_URL,
        "mode": "streaming",  # the only mode with a real time-to-first-token
        # Streaming has its own model namespace (batch's ``universal-2`` is not
        # valid here); ``universal-3-5-pro`` is accepted by the streaming API.
        "speech_model": "universal-3-5-pro",
        "realtime": True,
        "max_audio_seconds": max_audio_seconds,
        # Validate the transcript inline. ``contains`` is case-sensitive and the
        # clip says "wildfires" (lower-case, mid-sentence), so this really holds.
        "assertions": {"contains": "wildfires", "min_length": 50},
    }
    resp = client.post("/transcriptions/", json=payload)
    resp.raise_for_status()
    return resp.json()


def _print_pipeline_run(run: dict) -> None:
    print(f"\n[pipeline run] status={run['status']}")
    if run.get("error"):
        print(f"  error: {run['error']}")
    for node in run.get("node_results", []):
        kind = node.get("node_type")
        if kind == "assert":
            print(f"  - assert  {node['name']}: passed={node.get('passed')}")
        else:
            out = (node.get("output") or "").replace("\n", " ")
            print(f"  - {kind:<7} {node['name']}: {out[:100]}")
    if run.get("output"):
        print(f"  final output: {run['output'][:200]}")


def _print_test_case_run(name: str, run: dict) -> None:
    print(f"\n[test case] {name!r}: status={run['status']}")
    for result in run.get("results", []):
        flag = " [should_fail]" if result.get("should_fail") else ""
        print(
            f"  - {result['name']}{flag}: passed={result.get('passed')} "
            f"(assertions_held={result.get('assertions_held')})"
        )
    if run.get("error"):
        print(f"  error: {run['error']}")


def _print_transcription(metric: dict) -> None:
    print("\n[transcription] standalone streaming test")
    if metric.get("error"):
        print(f"  error: {metric['error']}")
        return
    print(f"  ttft_ms         : {metric.get('ttft_ms')}")
    print(f"  total_ms        : {metric.get('total_ms')}")
    print(f"  audio_duration  : {metric.get('audio_duration_ms')} ms")
    print(f"  real_time_factor: {metric.get('real_time_factor')}")
    print(f"  word_count      : {metric.get('word_count')}")
    print(f"  confidence      : {metric.get('confidence')}")
    print(f"  valid           : {metric.get('valid')}")
    print(f"  transcript      : {(metric.get('transcript') or '')[:160]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the seeded demo over the API.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--pipeline-name", default=DEFAULT_PIPELINE_NAME)
    parser.add_argument("--max-audio-seconds", type=int, default=25)
    parser.add_argument(
        "--skip-transcribe",
        action="store_true",
        help="skip the standalone transcription step (no ffmpeg / network needed)",
    )
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=_TIMEOUT) as client:
        token = _login(client, args.email, args.password)
        client.headers["Authorization"] = f"Bearer {token}"
        print(f"logged in as {args.email}")

        pipeline = _find_pipeline(client, args.pipeline_name)
        pid = pipeline["id"]
        print(f"pipeline: {pipeline['name']} ({pid})")

        _print_pipeline_run(_run_pipeline(client, pid))

        for test_case in _list_test_cases(client, pid):
            run = _run_test_case(client, pid, test_case["id"])
            _print_test_case_run(test_case["name"], run)

        if not args.skip_transcribe:
            _print_transcription(_transcribe(client, args.max_audio_seconds))

    print("\nDone. See /pipelines, /test-cases and /transcribe for the same data in the UI.")


if __name__ == "__main__":
    main()
