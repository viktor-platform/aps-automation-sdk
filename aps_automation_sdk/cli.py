"""
CLI entry-point for APS Automation SDK (``aps-automation`` command).

Commands::

    signing generate   Generate an RSA private key JSON.
    signing export     Export the public key JSON from a private key file.
    signing sign       Sign an activity ID with a private key.
    public-key info    Fetch the current forgeapps/me profile.
    public-key upload  Upload a public key JSON to forgeapps/me.

Credentials are resolved from ``CLIENT_ID`` and ``CLIENT_SECRET`` environment
variables or a ``.env`` file, with interactive prompts as a fallback.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv

from aps_automation_sdk.signing import export_public_key, generate_key_file, sign_activity
from aps_automation_sdk.utils import (
    get_forgeapp_profile,
    get_token,
    set_nickname,
    upload_public_key,
)


def resolve_client_credentials() -> Annotated[tuple[str, str], "Resolved APS client id and client secret"]:
    """
    Resolve ``CLIENT_ID`` and ``CLIENT_SECRET`` from environment variables or
    interactive prompts.

    Raises:
        ValueError: If either credential remains empty after prompting.
    """
    client_id = os.getenv("CLIENT_ID", "").strip()
    client_secret = os.getenv("CLIENT_SECRET", "").strip()

    if not client_id:
        client_id = input("APS CLIENT_ID: ").strip()
    if not client_secret:
        client_secret = getpass.getpass("APS CLIENT_SECRET: ").strip()

    if not client_id or not client_secret:
        raise ValueError("Missing CLIENT_ID or CLIENT_SECRET.")

    return client_id, client_secret


def resolve_token_from_credentials() -> Annotated[str, "2-legged OAuth access token"]:
    """Obtain a 2-legged OAuth bearer token using resolved client credentials."""
    client_id, client_secret = resolve_client_credentials()
    return get_token(client_id=client_id, client_secret=client_secret)


def run_signing_generate(args: Annotated[argparse.Namespace, "Parsed CLI arguments"]) -> Annotated[int, "Process exit code"]:
    """Handler for ``aps-automation signing generate``."""
    generate_key_file(keyfile=args.keyfile, key_size=args.key_size)
    print(f"Private key created at: {Path(args.keyfile).resolve()}")
    return 0


def run_signing_export(args: Annotated[argparse.Namespace, "Parsed CLI arguments"]) -> Annotated[int, "Process exit code"]:
    """Handler for ``aps-automation signing export``."""
    export_public_key(keyfile=args.keyfile, pubkeyfile=args.pubkeyfile)
    print(f"Public key created at: {Path(args.pubkeyfile).resolve()}")
    return 0


def run_signing_sign(args: Annotated[argparse.Namespace, "Parsed CLI arguments"]) -> Annotated[int, "Process exit code"]:
    """Handler for ``aps-automation signing sign``."""
    signature = sign_activity(keyfile=args.keyfile, activity_id=args.activity_id)
    print(signature)
    return 0


def run_public_key_info(args: Annotated[argparse.Namespace, "Parsed CLI arguments"]) -> Annotated[int, "Process exit code"]:
    """Handler for ``aps-automation public-key info``. Prints the forgeapps/me profile."""
    token = resolve_token_from_credentials()
    profile = get_forgeapp_profile(token=token)
    print(json.dumps(profile, indent=2))
    return 0


def load_public_key(
    pubkeyfile: Annotated[str, "Path to public key JSON file"],
) -> Annotated[dict[str, Any], "Parsed public key payload"]:
    """
    Read and lightly validate a public key JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the payload is not a non-empty JSON object.
    """
    path = Path(pubkeyfile)
    if not path.exists():
        raise FileNotFoundError(f"Public key file not found: {pubkeyfile}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Public key JSON must be a non-empty object")
    return payload


def run_public_key_upload(args: Annotated[argparse.Namespace, "Parsed CLI arguments"]) -> Annotated[int, "Process exit code"]:
    """Handler for ``aps-automation public-key upload``. Optionally sets a nickname first."""
    token = resolve_token_from_credentials()
    if args.nickname:
        applied = set_nickname(token=token, nickname=args.nickname)
        print(f"Using nickname: {applied}")

    public_key = load_public_key(args.pubkeyfile)
    response = upload_public_key(token=token, public_key=public_key)
    print(json.dumps(response, indent=2))
    return 0


def build_parser() -> Annotated[argparse.ArgumentParser, "Configured CLI parser"]:
    """
    Build and return the ``aps-automation`` ArgumentParser.

    Registers all subcommands and attaches handler functions via ``set_defaults``.
    """
    parser = argparse.ArgumentParser(prog="aps-automation", description="APS Automation SDK CLI")
    subparsers = parser.add_subparsers(dest="command")

    signing_parser = subparsers.add_parser("signing", help="Signing utilities")
    signing_subparsers = signing_parser.add_subparsers(dest="signing_command")

    generate_parser = signing_subparsers.add_parser("generate", help="Generate RSA private key JSON")
    generate_parser.add_argument("--keyfile", required=True, help="Output private key JSON path")
    generate_parser.add_argument("--key-size", type=int, default=2048, help="RSA key size")
    generate_parser.set_defaults(func=run_signing_generate)

    export_parser = signing_subparsers.add_parser("export", help="Export public key JSON from private key JSON")
    export_parser.add_argument("--keyfile", required=True, help="Input private key JSON path")
    export_parser.add_argument("--pubkeyfile", required=True, help="Output public key JSON path")
    export_parser.set_defaults(func=run_signing_export)

    sign_parser = signing_subparsers.add_parser("sign", help="Sign an activity id")
    sign_parser.add_argument("--keyfile", required=True, help="Input private key JSON path")
    sign_parser.add_argument("--activity-id", required=True, help="Activity id to sign")
    sign_parser.set_defaults(func=run_signing_sign)

    public_key_parser = subparsers.add_parser("public-key", help="forgeapps/me public key operations")
    public_key_subparsers = public_key_parser.add_subparsers(dest="public_key_command")

    info_parser = public_key_subparsers.add_parser("info", help="Get forgeapps/me profile")
    info_parser.set_defaults(func=run_public_key_info)

    upload_parser = public_key_subparsers.add_parser("upload", help="Upload public key to forgeapps/me")
    upload_parser.add_argument("--pubkeyfile", required=True, help="Public key JSON path")
    upload_parser.add_argument("--nickname", help="Optional nickname to set before upload")
    upload_parser.set_defaults(func=run_public_key_upload)

    return parser


def cli() -> Annotated[int, "Process exit code"]:
    """
    Main CLI entry-point invoked by the ``aps-automation`` console script.

    Returns 1 if no subcommand is given, 2 on handler errors.
    """
    load_dotenv(override=False)
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except Exception as exc:
        parser.exit(status=2, message=f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(cli())
