import base64
import json
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any


@lru_cache(maxsize=1)
def require_cryptography_modules() -> Annotated[tuple[ModuleType, ModuleType, ModuleType], "Loaded cryptography modules: hashes, padding, rsa"]:
    """
    Load cryptography modules lazily so the SDK can be imported without the signing extra.

    The result is cached so imports happen at most once per process.
    Raises ``RuntimeError`` with install instructions if the ``cryptography``
    package is not installed.
    """
    try:
        hashes = import_module("cryptography.hazmat.primitives.hashes")
        padding = import_module("cryptography.hazmat.primitives.asymmetric.padding")
        rsa = import_module("cryptography.hazmat.primitives.asymmetric.rsa")
    except ImportError as exc:
        raise RuntimeError(
            "Signing features require cryptography. Install with: uv add \"aps-automation-sdk[signing]\" (or pip install \"aps-automation-sdk[signing]\")."
        ) from exc
    return hashes, padding, rsa


def base64_encode(
    data: Annotated[bytes, "Raw bytes to encode as base64 text"],
) -> Annotated[str, "ASCII base64 encoded string"]:
    """Encode bytes as a standard (not URL-safe) base64 ASCII string."""
    return base64.b64encode(data).decode("ascii")


def base64_decode(
    text: Annotated[str, "ASCII base64 encoded string"],
) -> Annotated[bytes, "Decoded raw bytes"]:
    """Decode a standard base64 ASCII string back to raw bytes."""
    return base64.b64decode(text)


def int_to_bytes(
    value: Annotated[int, "Positive integer to convert to big-endian bytes"],
) -> Annotated[bytes, "Big-endian bytes"]:
    """Convert a positive integer to its minimal big-endian byte representation."""
    byte_length = (value.bit_length() + 7) // 8
    return value.to_bytes(byte_length, byteorder="big")


def bytes_to_int(
    data: Annotated[bytes, "Big-endian bytes to convert into integer"],
) -> Annotated[int, "Converted integer value"]:
    """Interpret big-endian bytes as an unsigned integer."""
    return int.from_bytes(data, byteorder="big")


def generate_key_file(
    keyfile: Annotated[str, "Path to write private key JSON file"],
    key_size: Annotated[int, "RSA key size in bits (recommended 2048)"] = 2048,
) -> Annotated[str, "Absolute path where the private key JSON file was saved"]:
    """
    Generate an RSA private key file in Autodesk signer-compatible JSON format.

    Writes a JSON file with base64-encoded CRT components (D, DP, DQ, Exponent,
    InverseQ, Modulus, P, Q). Keep this file secret and never commit it to
    source control. Use ``export_public_key`` to extract the public portion.

    Returns:
        Absolute path of the written key file.
    """
    _, _, rsa = require_cryptography_modules()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_numbers = private_key.private_numbers()
    public_numbers = private_numbers.public_numbers

    key_data = {
        "D": base64_encode(int_to_bytes(private_numbers.d)),
        "DP": base64_encode(int_to_bytes(private_numbers.dmp1)),
        "DQ": base64_encode(int_to_bytes(private_numbers.dmq1)),
        "Exponent": base64_encode(int_to_bytes(public_numbers.e)),
        "InverseQ": base64_encode(int_to_bytes(private_numbers.iqmp)),
        "Modulus": base64_encode(int_to_bytes(public_numbers.n)),
        "P": base64_encode(int_to_bytes(private_numbers.p)),
        "Q": base64_encode(int_to_bytes(private_numbers.q)),
    }

    output_path = Path(keyfile)
    output_path.write_text(json.dumps(key_data, indent=2), encoding="utf-8")
    return str(output_path.resolve())


def export_public_key(
    keyfile: Annotated[str, "Path to existing private key JSON file"],
    pubkeyfile: Annotated[str, "Path to write exported public key JSON file"],
) -> None:
    """
    Export only the public key fields (Exponent and Modulus) from a private key JSON.

    The resulting file is safe to share and is the payload expected by
    ``upload_public_key`` / ``aps-automation public-key upload``.
    """
    key_path = Path(keyfile)
    if not key_path.exists():
        raise FileNotFoundError(f"Key file not found: {keyfile}")

    key_data = json.loads(key_path.read_text(encoding="utf-8"))
    public_key_data = {
        "Exponent": key_data["Exponent"],
        "Modulus": key_data["Modulus"],
    }

    output_path = Path(pubkeyfile)
    output_path.write_text(json.dumps(public_key_data, indent=2), encoding="utf-8")


def load_private_key_data(
    keyfile: Annotated[str, "Path to private key JSON file"],
) -> Annotated[dict[str, Any], "Parsed private key payload"]:
    """
    Load and validate a private key JSON file produced by ``generate_key_file``.

    Raises:
        FileNotFoundError: If the key file does not exist.
        ValueError: If required CRT fields (D, Exponent, InverseQ, Modulus, P, Q)
            are missing from the payload.
    """
    key_path = Path(keyfile)
    if not key_path.exists():
        raise FileNotFoundError(f"Key file not found: {keyfile}")
    key_data = json.loads(key_path.read_text(encoding="utf-8"))
    required = ["D", "Exponent", "InverseQ", "Modulus", "P", "Q"]
    missing = [field for field in required if field not in key_data]
    if missing:
        raise ValueError(f"Invalid key file. Missing fields: {', '.join(missing)}")
    return key_data


def sign_activity(
    keyfile: Annotated[str, "Path to private key JSON file used for signing"],
    activity_id: Annotated[str, "Full activity id in format nickname.Activity+alias"],
) -> Annotated[str, "Base64 RSA-SHA256 signature for the activity id"]:
    """
    Sign an activity ID with RSA-SHA256 PKCS#1 v1.5 and return a base64 signature.

    The activity ID is encoded as UTF-16-LE before signing, matching the encoding
    expected by APS for workitem signature verification.

    Args:
        keyfile: Path to a private key JSON file produced by ``generate_key_file``.
        activity_id: Full activity identifier in ``nickname.Activity+alias`` form.

    Returns:
        Base64-encoded signature to pass as ``activity_signature`` in
        ``WorkItemAcc.run_public_activity``.
    """
    hashes, padding, rsa = require_cryptography_modules()
    key_data = load_private_key_data(keyfile)

    d = bytes_to_int(base64_decode(key_data["D"]))
    p = bytes_to_int(base64_decode(key_data["P"]))
    q = bytes_to_int(base64_decode(key_data["Q"]))
    e = bytes_to_int(base64_decode(key_data["Exponent"]))
    n = bytes_to_int(base64_decode(key_data["Modulus"]))
    iqmp = bytes_to_int(base64_decode(key_data["InverseQ"]))

    dmp1 = bytes_to_int(base64_decode(key_data["DP"])) if "DP" in key_data else d % (p - 1)
    dmq1 = bytes_to_int(base64_decode(key_data["DQ"])) if "DQ" in key_data else d % (q - 1)

    private_numbers = rsa.RSAPrivateNumbers(
        p=p,
        q=q,
        d=d,
        dmp1=dmp1,
        dmq1=dmq1,
        iqmp=iqmp,
        public_numbers=rsa.RSAPublicNumbers(e=e, n=n),
    )
    private_key = private_numbers.private_key()

    message = activity_id.encode("utf-16-le")
    signature = private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return base64_encode(signature)
