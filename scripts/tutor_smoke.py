"""Run two authenticated visits against an already running API, recording real usage.

No model calls or tokens are simulated. Non-LLM or uncached responses fail the check.
"""
import argparse
import json
import os
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    token = os.environ.get("MASTRR_API_TOKEN") or os.environ.get("LOCAL_API_TOKEN")
    if not token:
        parser.error("Set MASTRR_API_TOKEN (or LOCAL_API_TOKEN) in the environment.")
    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}):
        parser.error("Use HTTPS for a hosted API, or HTTP on loopback only.")
    url = args.base_url.rstrip("/") + "/v1/me/tutor/" + quote(args.topic, safe="")
    results = []
    for _ in range(2):
        request = Request(url, method="POST", headers={"Authorization": f"Bearer {token}"})
        with urlopen(request, timeout=240) as response:
            results.append(json.load(response))
    for i, result in enumerate(results, 1):
        print(json.dumps({"visit": i, "generated_by": result["generated_by"],
                          "cached": {k: v["cached"] for k, v in result["parts"].items()},
                          "usage": result["usage"]}, indent=2))
    if results[0]["generated_by"] != "llm":
        raise SystemExit("Live check incomplete: needs reviewed notes, completed mistakes and a working provider key.")
    if not all(p["cached"] for p in results[1]["parts"].values()) or results[1]["usage"]:
        raise SystemExit("Cache check failed: second visit should use both caches and make no provider calls.")


if __name__ == "__main__":
    main()
