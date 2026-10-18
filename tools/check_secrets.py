"""Secret hygiene checks that never print credential values."""
from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SECRETS_DIR = ROOT / "secrets"
ENV_FILE = SECRETS_DIR / ".env"
REQUIRED = (
    "WIFI_SSID", "WIFI_PASSWORD", "THINGSPEAK_API_KEY", "FIREBASE_PROJECT_ID",
    "FIREBASE_API_KEY", "FIREBASE_DATABASE_URL", "FIREBASE_DEVICE_EMAIL",
    "FIREBASE_DEVICE_PASSWORD", "FIREBASE_DEVICE_UID", "FIREBASE_APP_USER_EMAIL",
    "VAPID_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
)
SKIP_PARTS = {".git", ".pio", "node_modules", "canvaskit", "__pycache__", "secrets"}
MAX_FILE_BYTES = 2_000_000


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def placeholder(value: str) -> bool:
    return not value or any(token in value.upper() for token in ("YOUR_", "REPLACE_", "CHANGE_ME", "<"))


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            if path.stat().st_size <= MAX_FILE_BYTES:
                yield path
        except OSError:
            continue


def check_history() -> str:
    if not (ROOT / ".git").exists():
        return "NOT RUN: Git metadata is absent"
    result = subprocess.run(["git", "log", "--all", "--oneline", "-S", "WIFI_PASSWORD"], cwd=ROOT, capture_output=True, text=True)
    return "FAILED: Git history contains Wi-Fi credential references; rotate affected credentials" if result.stdout.strip() else "PASSED"


def main() -> int:
    outcomes: list[tuple[str, str]] = []
    values = load_env(ENV_FILE)
    missing = [name for name in REQUIRED if placeholder(values.get(name, ""))]
    outcomes.append(("required variables", "PASSED" if not missing else "FAILED: missing/placeholder " + ", ".join(missing)))

    leaks: list[str] = []
    private_values = [value for value in values.values() if value and not placeholder(value) and "service-account.json" not in value]
    for path in iter_files():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(value in content for value in private_values):
            leaks.append(str(path.relative_to(ROOT)))
    outcomes.append(("private values outside secrets/", "PASSED" if not leaks else "FAILED: " + ", ".join(sorted(set(leaks)))))

    accounts = [str(path.relative_to(ROOT)) for path in iter_files() if re.search(r"(serviceAccount.*\.json|.*-firebase-adminsdk-.*\.json)$", path.name, re.I)]
    outcomes.append(("service-account files outside secrets/", "PASSED" if not accounts else "FAILED: " + ", ".join(accounts)))
    outcomes.append(("Git history", check_history()))
    outcomes.append(("build/web scan", "NOT RUN: build/web is absent" if not (ROOT / "build" / "web").exists() else "NOT RUN: no private secret scan is possible until secrets/.env is configured"))

    failed = False
    for label, result in outcomes:
        print(f"{label}: {result}")
        failed = failed or result.startswith("FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
