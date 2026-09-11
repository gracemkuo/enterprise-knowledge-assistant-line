#!/usr/bin/env python3
"""Rotate the WhatsApp access token and update the deployed Cloud Run service."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import urllib.error
import urllib.request


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from enterprise_knowledge_assistant.config import Settings  # noqa: E402


DEFAULT_REGION = "asia-east1"
DEFAULT_SERVICE = "enterprise-knowledge-assistant-line"
DEFAULT_SECRET = "eka-whatsapp-access-token"


class RotationError(RuntimeError):
    """An expected, safely reportable token-rotation failure."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a WhatsApp token, ensure the current Meta App is subscribed "
            "to its WABA, add a Secret Manager version, update Cloud Run, and run "
            "smoke tests. The token is never accepted as a command-line argument."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPOSITORY_ROOT / ".env",
        help="dotenv file to read and update (default: repository .env)",
    )
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="use WHATSAPP_ACCESS_TOKEN already stored in the dotenv file",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="validate Meta and Cloud Run state without changing anything",
    )
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET)
    return parser.parse_args()


def request_json(
    url: str,
    token: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            error = json.loads(exc.read()).get("error", {})
        except (json.JSONDecodeError, UnicodeDecodeError):
            error = {}
        details = ", ".join(
            part
            for part in (
                f"HTTP {exc.code}",
                f"code {error.get('code')}" if error.get("code") else "",
                (
                    f"subcode {error.get('error_subcode')}"
                    if error.get("error_subcode")
                    else ""
                ),
                str(error.get("message") or ""),
            )
            if part
        )
        raise RotationError(f"Meta Graph API request failed: {details}") from exc
    except urllib.error.URLError as exc:
        raise RotationError(f"Meta Graph API is unreachable: {exc.reason}") from exc


def subscription_app_ids(payload: dict[str, Any]) -> set[str]:
    app_ids: set[str] = set()
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        nested = item.get("whatsapp_business_api_data") or {}
        app_id = nested.get("id") if isinstance(nested, dict) else None
        app_id = app_id or item.get("id")
        if app_id:
            app_ids.add(str(app_id))
    return app_ids


def ensure_waba_subscription(settings: Settings, token: str) -> bool:
    url = (
        f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/"
        f"{settings.whatsapp_business_account_id}/subscribed_apps"
    )
    existing = request_json(url, token)
    if settings.meta_app_id in subscription_app_ids(existing):
        print("[ok] Current Meta App is already subscribed to the WABA.")
        return False

    result = request_json(url, token, method="POST", data=b"")
    if result.get("success") is not True:
        raise RotationError("Meta did not confirm the WABA subscription.")

    verified = request_json(url, token)
    if settings.meta_app_id not in subscription_app_ids(verified):
        raise RotationError("WABA subscription was not visible after Meta accepted it.")

    print("[ok] Subscribed the current Meta App to the WABA.")
    return True


def update_env_token(path: Path, token: str) -> None:
    original = path.read_text(encoding="utf-8")
    replacement = f"WHATSAPP_ACCESS_TOKEN={json.dumps(token)}"
    updated, count = re.subn(
        r"^WHATSAPP_ACCESS_TOKEN=.*$",
        replacement,
        original,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        separator = "" if not original or original.endswith("\n") else "\n"
        updated = f"{original}{separator}{replacement}\n"

    current_mode = path.stat().st_mode & 0o777
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        os.fchmod(descriptor, current_mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(updated)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def run_gcloud(arguments: list[str], *, stdin: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["gcloud", *arguments],
            input=stdin,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "gcloud command failed").strip()
        raise RotationError(detail) from exc
    return result.stdout.strip()


def current_cloud_run_secret_version(
    project: str, region: str, service: str
) -> str | None:
    raw = run_gcloud(
        [
            "run",
            "services",
            "describe",
            service,
            f"--project={project}",
            f"--region={region}",
            "--format=json",
        ]
    )
    service_data = json.loads(raw)
    containers = (
        service_data.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    for variable in (containers[0].get("env", []) if containers else []):
        if variable.get("name") == "WHATSAPP_ACCESS_TOKEN":
            return (
                variable.get("valueFrom", {})
                .get("secretKeyRef", {})
                .get("key")
            )
    return None


def add_secret_version(project: str, secret_name: str, token: str) -> str:
    version_name = run_gcloud(
        [
            "secrets",
            "versions",
            "add",
            secret_name,
            f"--project={project}",
            "--data-file=-",
            "--format=value(name)",
        ],
        stdin=token,
    )
    version = version_name.rsplit("/", 1)[-1]
    if not version.isdigit():
        raise RotationError("Could not determine the new Secret Manager version.")
    print(f"[ok] Added Secret Manager version {version}.")
    return version


def update_cloud_run(
    project: str,
    region: str,
    service: str,
    secret_name: str,
    secret_version: str,
) -> str:
    revision = run_gcloud(
        [
            "run",
            "services",
            "update",
            service,
            f"--project={project}",
            f"--region={region}",
            (
                "--update-secrets="
                f"WHATSAPP_ACCESS_TOKEN={secret_name}:{secret_version}"
            ),
            "--quiet",
            "--format=value(status.latestReadyRevisionName)",
        ]
    )
    if not revision:
        raise RotationError("Cloud Run did not return a ready revision name.")
    print(f"[ok] Cloud Run is serving revision {revision}.")
    return revision


def cloud_run_url(project: str, region: str, service: str) -> str:
    url = run_gcloud(
        [
            "run",
            "services",
            "describe",
            service,
            f"--project={project}",
            f"--region={region}",
            "--format=value(status.url)",
        ]
    )
    if not url.startswith("https://"):
        raise RotationError("Cloud Run did not return an HTTPS service URL.")
    return url.rstrip("/")


def http_response(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise RotationError(f"Cloud Run is unreachable: {exc.reason}") from exc


def smoke_test_cloud_run(settings: Settings, service_url: str) -> None:
    health_status, _ = http_response(f"{service_url}/health")
    if health_status != 200:
        raise RotationError(f"Health check returned HTTP {health_status}.")
    print("[ok] Cloud Run health check returned HTTP 200.")

    verify_status, _ = http_response(f"{service_url}/webhooks/whatsapp")
    if verify_status != 403:
        raise RotationError(
            "WhatsApp webhook accepted a verification request without a token."
        )
    print("[ok] WhatsApp verification endpoint rejected a missing token.")

    body = b'{"object":"whatsapp_business_account","entry":[]}'
    signature = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    post_status, _ = http_response(
        f"{service_url}/webhooks/whatsapp",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    if post_status != 200:
        raise RotationError(
            f"Signed WhatsApp webhook smoke test returned HTTP {post_status}."
        )
    print("[ok] Signed WhatsApp webhook returned HTTP 200.")


def validate_settings(settings: Settings) -> None:
    required = {
        "META_APP_ID": settings.meta_app_id,
        "WHATSAPP_BUSINESS_ACCOUNT_ID": settings.whatsapp_business_account_id,
        "WHATSAPP_PHONE_NUMBER_ID": settings.whatsapp_phone_number_id,
        "WHATSAPP_VERIFY_TOKEN": settings.whatsapp_verify_token,
        "WHATSAPP_APP_SECRET": settings.whatsapp_app_secret,
        "GOOGLE_CLOUD_PROJECT": settings.google_cloud_project,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RotationError("Missing settings: " + ", ".join(missing))


def main() -> int:
    args = parse_args()
    if not args.env_file.is_file():
        raise RotationError(f"Environment file not found: {args.env_file}")
    if shutil.which("gcloud") is None and not args.check_only:
        raise RotationError("gcloud is not installed or not available in PATH.")

    settings = Settings(_env_file=args.env_file)  # type: ignore[call-arg]
    validate_settings(settings)
    token = (
        settings.whatsapp_access_token
        if args.from_env
        else getpass.getpass("Paste the new WhatsApp access token: ").strip()
    )
    if not token:
        raise RotationError("The WhatsApp access token is empty.")

    subscription_url = (
        f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/"
        f"{settings.whatsapp_business_account_id}/subscribed_apps"
    )
    subscription = request_json(subscription_url, token)
    is_subscribed = settings.meta_app_id in subscription_app_ids(subscription)
    print(f"[check] Current Meta App subscribed: {str(is_subscribed).lower()}")

    if args.check_only:
        return 0 if is_subscribed else 2

    ensure_waba_subscription(settings, token)
    if not args.from_env:
        update_env_token(args.env_file, token)
        print(f"[ok] Updated {args.env_file} without printing the token.")

    previous_version = current_cloud_run_secret_version(
        settings.google_cloud_project, args.region, args.service
    )
    new_version = add_secret_version(
        settings.google_cloud_project, args.secret_name, token
    )
    update_cloud_run(
        settings.google_cloud_project,
        args.region,
        args.service,
        args.secret_name,
        new_version,
    )
    service_url = cloud_run_url(
        settings.google_cloud_project, args.region, args.service
    )
    smoke_test_cloud_run(settings, service_url)

    print(f"[done] Service URL: {service_url}")
    if previous_version:
        print(
            "[rollback] Previous secret version was "
            f"{previous_version}; see docs/whatsapp-token-rotation.md."
        )
    print("[next] Send a new WhatsApp text message from an allowlisted phone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RotationError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
