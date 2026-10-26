"""Run an isolated, explicitly labelled recording demo, with optional live Groq."""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from backend.demo import ROOT, DEMO_ROOT, MARKER, prepare_demo
from backend.local_env import load_local_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "serve", "check-live", "stop"])
    parser.add_argument("--sample-content", action="store_true", help="acknowledge these are unreviewed demonstration samples")
    parser.add_argument("--live", action="store_true", help="enable real Groq calls using the private local key")
    parser.add_argument("--topic", default="divisibility")
    parser.add_argument("--seed-mistakes", action="store_true", help="complete a labelled sample diagnostic using I don't know")
    args = parser.parse_args()
    load_local_env()
    if args.command == "stop":
        try:
            active = json.loads((DEMO_ROOT / "active.json").read_text(encoding="utf-8"))
            folder = Path(active["folder"]).resolve()
            if active["kind"] != MARKER or not folder.is_relative_to(DEMO_ROOT.resolve()):
                raise ValueError
            (folder / "stop-requested").touch()
        except (OSError, ValueError, KeyError):
            parser.error("No valid active demo was found.")
        print("Stop requested for the demo's own child processes.")
        return
    if args.command == "check-live":
        from scripts.tutor_smoke import main as smoke
        manifest = json.loads((DEMO_ROOT / "active.json").read_text(encoding="utf-8"))
        token_path = Path(manifest["token_file"]).resolve()
        if not token_path.is_relative_to(DEMO_ROOT.resolve()):
            parser.error("Invalid demo token path.")
        os.environ["MASTRR_API_TOKEN"] = token_path.read_text(encoding="utf-8")
        sys.argv = ["tutor_smoke", manifest["topic"], "--base-url", "http://127.0.0.1:8880"]
        smoke()
        return
    if not args.sample_content:
        parser.error("Use --sample-content to acknowledge this separate database uses unreviewed demo samples.")
    if args.live and not os.environ.get("GROQ_API_KEY"):
        parser.error("Live mode needs a replacement GROQ_API_KEY in the private root .env or process environment. No key is printed.")
    node = shutil.which("node")
    if args.command == "serve" and (not node or not (ROOT / "frontend/node_modules/next/dist/bin/next").is_file()):
        parser.error("Install Node 22+ and run npm ci inside frontend/ first.")
    if args.command == "serve":
        for port in (8880, 3001):
            with socket.socket() as probe:
                probe.settimeout(1)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    parser.error(f"Port {port} is already in use. Stop that demo before starting another.")
    manifest = prepare_demo(args.topic, args.seed_mistakes)
    print("Isolated demo prepared. Source drafts and data/local.db were not changed.")
    print("Local sign-in token file:", manifest["token_file"])
    if args.command == "prepare":
        return
    backend_env = {**os.environ, "DATABASE_URL": manifest["database_url"], "LOCAL_DEVELOPMENT": "1",
        "LOCAL_API_TOKEN": Path(manifest["token_file"]).read_text(encoding="utf-8"), "MASTRR_DEMO": "1",
        "MASTRR_ENV": "development", "MASTRR_ADMIN_SUBJECTS": "local-developer",
        "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", "") if args.live else ""}
    frontend_env = {k: v for k, v in os.environ.items() if k not in {"GROQ_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "LOCAL_API_TOKEN", "DATABASE_URL"}}
    frontend_env.update(NEXT_PUBLIC_LOCAL_DEVELOPMENT="1", NEXT_PUBLIC_SUPABASE_URL="", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY="",
                        MASTRR_API_ORIGIN="http://127.0.0.1:8880", NEXT_TELEMETRY_DISABLED="1", MASTRR_DEMO_FRONTEND="1")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    processes, logs = [], []
    try:
        (DEMO_ROOT / "active.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        for name, command, cwd, environment in (
            ("api", [sys.executable, "-m", "uvicorn", "backend.api:create_app", "--factory", "--host", "127.0.0.1", "--port", "8880"], ROOT, backend_env),
            ("frontend", [node, "node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1", "--port", "3001"], ROOT / "frontend", frontend_env),
        ):
            output = open(Path(manifest["folder"]) / (name + ".log"), "w", encoding="utf-8")
            logs.append(output)
            processes.append(subprocess.Popen(command, cwd=cwd, env=environment, stdout=output, stderr=subprocess.STDOUT, creationflags=flags))
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in processes):
                raise RuntimeError("A demo process stopped. Inspect the logs in the demo folder; no credentials are printed.")
            try:
                with urlopen("http://127.0.0.1:8880/ready", timeout=2):
                    pass
                with urlopen("http://127.0.0.1:3001/login", timeout=3):
                    pass
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Demo startup timed out. Inspect the logs in its isolated folder.")
        print("Demo ready: http://127.0.0.1:3001")
        print("AI mode:", "LIVE Groq; calls may consume your allowance" if args.live else "OFFLINE; labelled notes and answer fallbacks")
        print("Use the token file to sign in. Stop with python -m scripts.demo stop, or press Ctrl+C here.", flush=True)
        while all(p.poll() is None for p in processes) and not (Path(manifest["folder"]) / "stop-requested").exists():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for output in logs:
            output.close()
        active_path = DEMO_ROOT / "active.json"
        if active_path.is_file():
            try:
                if json.loads(active_path.read_text(encoding="utf-8")).get("folder") == manifest["folder"]:
                    active_path.unlink()
            except (OSError, ValueError):
                pass


if __name__ == "__main__":
    main()
