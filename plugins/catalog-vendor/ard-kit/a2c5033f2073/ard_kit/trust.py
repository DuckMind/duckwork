#!/usr/bin/env python3
"""Trust verdicts for ARD entries: screen, bind, verify.

The ARD spec (§4.5) says a registry MUST verify that a resource's manifest is
hosted on — or cryptographically bound to — the domain its URN claims, and
MUST NOT let a relevance score be read as trust. Search answers "does this
match the words"; nothing in a ranked list answers "may I believe this".

Four verdicts, in descending order of belief:

  VERIFIED    evidence beyond the entry's own text: the manifest was fetched
              from the domain the URN claims (--url), or a detached signature
              over the attestation verified against the issuer's JWKS
              (--attestation). Identity bound, screening clean.
  UNVERIFIED  nothing wrong, nothing proven. No trustManifest, or a manifest
              that only asserts its own binding. This is the honest verdict
              for a locally catalogized directory.
  SUSPECT     a positive reason not to believe it: prompt-injection markers,
              invisible/bidi characters, a shell-chained invoke command, a
              manifest whose identity does not match the URN authority, or a
              manifest served by one domain listing another domain's URN.
  UNSUPPORTED a check was asked for that this install cannot perform: an
              identity scheme that is not did:web, or a detached JWS with no
              `cryptography` available.

Federation uses this as a gate: `registry.federated_search` drops peer rows
that come back SUSPECT, because a peer's displayName and description land
verbatim in an agent's context.

ponytail: the injection screen is a curated marker list, not a classifier —
it catches the shapes that have been seen in the wild and nothing else. It is
calibrated against the live station catalog (1706 entries, 0 false positives),
so a hit is worth reading rather than noise. Upgrade path: swap `_INJECTION`
for a model call behind the same `screen_entry()` signature.

Usage:
    ard-verify --catalog ai-catalog.json
    ard-verify --url https://ora.ai                # hosted = evidence
    ard-verify --attestation att.json --jwks https://ora.ai/.well-known/jwks.json
    python3 -m ard_kit.trust --catalog ai-catalog.json --json
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from ard_kit.catalogize import guard_posix_paths

# ponytail: the runtime is stdlib-only by declared invariant (see the header of
# pyproject.toml), so Ed25519 is guard-imported rather than depended on. The
# ceiling: without `cryptography` a detached JWS cannot be checked at all, and
# the verdict says so loudly instead of quietly downgrading to UNVERIFIED.
# Upgrade path: an optional `[trust]` extra naming cryptography.
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
except ImportError:  # pragma: no cover - depends on the install
    Ed25519PublicKey = None  # type: ignore[assignment]

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
SUSPECT = "SUSPECT"
UNSUPPORTED = "UNSUPPORTED"

# Precedence when one entry collects findings from several checks: the worst
# verdict wins, so a bound identity can never launder an injection marker.
_RANK = {VERIFIED: 0, UNVERIFIED: 1, UNSUPPORTED: 2, SUSPECT: 3}

# What a non-zero exit and --quiet both mean: rows that are actively bad, plus
# rows we could not check at all. UNVERIFIED is deliberately absent - an honest
# entry with nothing to prove is the normal result, and flagging it would fail
# every catalog on earth.
_FLAGGED = (SUSPECT, UNSUPPORTED)

# C0/C1 control characters (tab and newline are legitimate in prose), plus the
# invisible formatting set used for both token smuggling and bidi spoofing:
# soft hyphen, combining grapheme joiner, zero-widths, bidi overrides and the
# bidi isolates, word joiner, BOM. Two additions are smuggler-specific: the
# Hangul fillers render blank (U+3164 is the classic "invisible character"),
# and the TAG block is the canonical prompt-injection steganography channel -
# hidden from a human reader, still present for the model. VS16 (U+FE0F) is
# deliberately NOT listed: legitimate emoji presentation would make it a
# false positive on honest cards.
_INVISIBLE = re.compile(
    "[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f"
    "\u00ad\u034f\u115f\u1160\u180e\u200b-\u200f\u202a-\u202e"
    "\u2060-\u2064\u2066-\u2069\u3164\ufeff\uffa0"
    "\U000e0000-\U000e007f]"
)

_INJECTION = (
    re.compile(
        r"(?i)\b(ignore|disregard|forget|override)\b.{0,24}\b(previous|prior|"
        r"above|earlier|all|any|your)\b.{0,24}\b(instructions?|rules?|prompts?|"
        r"context|guidance)\b"
    ),
    re.compile(r"(?i)\byou are (now|no longer|henceforth)\b"),
    re.compile(r"(?i)\bnew (system )?instructions?\s*:"),
    re.compile(
        r"(?i)\b(reveal|show|print|leak|exfiltrate|repeat|output|dump)\b.{0,40}"
        r"\bsystem prompt\b"
    ),
    re.compile(
        r"(?i)\bdo not (tell|inform|mention to|notify|reveal to)\b.{0,20}"
        r"\b(the )?(user|operator|human|owner)\b"
    ),
    # Markup that a renderer or a browser will act on rather than display.
    re.compile(r"(?i)<\s*/?\s*(script|iframe|object|embed|svg|img|link|meta)\b"),
    re.compile(r"(?i)\b(curl|wget)\b[^\n]{0,200}\|\s*(ba|z|da|fi)?sh\b"),
)

# A command that runs a second command. Variable expansion ($HOME), quoting
# and `exec` are normal in a launcher line and must not trip this — the
# station's own 12 MCP cards are `bash -lc '[exec ]$HOME/.../run.sh'` and are
# legitimate. Measured against the live 1706-entry station catalog: 0 hits.
_SHELL_CHAIN = re.compile(r"[;`]|\|\||&&|\||\$\(|\beval\b")

# Schemes a resource URL may use. Anything else is a renderer or a resolver
# being asked to do something the catalog has no business requesting.
_URL_SCHEMES = ("http:", "https:", "file:", "urn:")

# Ceilings calibrated on the live station catalog (1706 entries, measured
# 2026-09-04: displayName max 45, description max 401, 10 list items, longest
# item 401). Every cap sits well above honest local content, so a hit is a
# peer padding a field rather than noise. List items share the description
# cap: a separate tighter one flagged our own MCP cards' representativeQueries.
_MAX_DISPLAY_NAME = 200
_MAX_DESCRIPTION = 2000
_MAX_LIST_ITEMS = 64


def _walk_strings(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield (json-path, text) for every string in a nested JSON value."""
    if isinstance(value, str):
        yield path or "$", value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_strings(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{path}[{index}]")


def screen_text(label: str, text: str) -> list[str]:
    """Screen one string; return findings, empty when clean."""
    findings: list[str] = []
    hit = _INVISIBLE.search(text)
    if hit:
        findings.append(
            f"{label}: invisible/control character U+{ord(hit.group()):04X} "
            f"at offset {hit.start()}"
        )
    for pattern in _INJECTION:
        match = pattern.search(text)
        if match:
            findings.append(
                f"{label}: injection marker {match.group(0)!r}"
            )
            break  # one marker per string is enough to act on
    return findings


def screen_entry(entry: dict[str, Any]) -> list[str]:
    """Screen a whole catalog entry; return findings, empty when clean.

    Every string anywhere in the entry is screened, because a peer controls
    all of them and any of them can be echoed into an agent's context. The
    field-specific rules below only add what a whole-entry walk cannot see.
    """
    findings: list[str] = []
    for path, text in _walk_strings(entry):
        findings.extend(screen_text(path, text))

    name = str(entry.get("displayName") or "")
    if len(name) > _MAX_DISPLAY_NAME:
        findings.append(
            f"displayName: {len(name)} chars over the {_MAX_DISPLAY_NAME} cap"
        )
    description = str(entry.get("description") or "")
    if len(description) > _MAX_DESCRIPTION:
        findings.append(
            f"description: {len(description)} chars over the "
            f"{_MAX_DESCRIPTION} cap"
        )
    for field in ("tags", "aliases", "capabilities", "representativeQueries"):
        items = entry.get(field)
        if isinstance(items, list) and len(items) > _MAX_LIST_ITEMS:
            findings.append(
                f"{field}: {len(items)} items over the {_MAX_LIST_ITEMS} cap"
            )
        for item in items if isinstance(items, list) else []:
            if isinstance(item, str) and len(item) > _MAX_DESCRIPTION:
                findings.append(
                    f"{field}: item of {len(item)} chars over the "
                    f"{_MAX_DESCRIPTION} cap"
                )
                break

    url = str(entry.get("url") or "")
    if url and not url.startswith(_URL_SCHEMES):
        findings.append(f"url: scheme not in {_URL_SCHEMES}: {url[:48]!r}")

    metadata = entry.get("metadata")
    invoke = str((metadata or {}).get("invoke") or "") if isinstance(
        metadata, dict
    ) else ""
    match = _SHELL_CHAIN.search(invoke)
    if match:
        findings.append(
            f"metadata.invoke: shell chaining {match.group(0)!r} in "
            f"{invoke[:64]!r}"
        )
    return findings


def urn_authority(identifier: str) -> str | None:
    """Return the domain a `urn:air:<domain>:<kind>:<rest>` URN claims."""
    parts = identifier.split(":")
    if len(parts) < 4 or parts[0].lower() != "urn" or parts[1].lower() != "air":
        return None
    return parts[2].lower() or None


def identity_domain(identity: str) -> tuple[str | None, str]:
    """Split a manifest identity into (checkable domain, reason if not).

    did:web is the only scheme whose domain can be compared to a URN
    authority offline; §4.5.1 also allows SPIFFE and ANS, and neither maps to
    a DNS name without a resolver this kit does not carry.
    """
    lowered = identity.strip().lower()
    if lowered.startswith("did:web:"):
        rest = lowered[len("did:web:"):]
        # did:web permits path segments and a percent-encoded port; the trust
        # domain is the first segment.
        host = rest.split(":")[0].split("%3A")[0]
        return (host or None), ""
    parts = lowered.split(":")
    # A DID's scheme is `did:<method>`; reporting bare "did" hides which method
    # we could not resolve, which is the only actionable part of the message.
    scheme = ":".join(parts[:2]) if parts[0] == "did" and len(parts) > 1 else parts[0]
    return None, f"identity scheme {scheme or 'unknown'!r} is not did:web"


def bind_identity(
    entry: dict[str, Any],
) -> tuple[bool | None, str | None, list[str]]:
    """Check §4.5.1: does the manifest identity match the URN authority?

    Returns (bound, identity, findings). `bound` is None when there is nothing
    to bind — no manifest, or a scheme this install cannot check.
    """
    manifest = entry.get("trustManifest")
    if not isinstance(manifest, dict):
        return None, None, []
    identity = manifest.get("identity")
    if not isinstance(identity, str) or not identity.strip():
        return None, None, ["trustManifest.identity is missing or not a string"]

    authority = urn_authority(str(entry.get("identifier") or ""))
    if authority is None:
        return None, identity, [
            f"identifier is not a urn:air:<domain>:... URN: "
            f"{str(entry.get('identifier'))[:64]!r}"
        ]

    domain, reason = identity_domain(identity)
    if domain is None:
        return None, identity, [reason]
    if domain != authority:
        return False, identity, [
            f"identity {identity!r} does not match URN authority {authority!r}"
        ]
    return True, identity, []


def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def canonical_payload(attestation: dict[str, Any]) -> bytes:
    """Serialize the signed body of a detached attestation.

    Ora publishes detached Ed25519 JWS over its agent-readiness scorecards and
    does not document the canonicalization. Measured against the live
    signature on 2026-09-04 over five candidate serializations, exactly one
    verified: the served object minus `jws` and `signed`, compact separators,
    keys sorted. Recorded in evidence/ard-phase-c-gate-2026-09-04/.

    ponytail: one issuer's undocumented choice, hard-coded because it is the
    only detached-ARD-JWS producer in the wild. Ceiling: an issuer that sorts
    differently fails closed to "signature did not verify", never to VERIFIED.
    Upgrade path: try a small ordered candidate list and report which matched.
    """
    body = {k: v for k, v in attestation.items() if k not in ("jws", "signed")}
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")


def verify_jws(
    attestation: dict[str, Any], jwks: dict[str, Any]
) -> tuple[bool | None, str]:
    """Verify a JWS over an attestation against a JWKS, attached or detached.

    Returns (ok, detail). `ok` is None when the check could not be performed
    (no signature, unsupported algorithm, missing key, no crypto library) —
    which is UNSUPPORTED, not a failure. `ok` is False only when every input
    was present and the signature did not verify.
    """
    jws = attestation.get("jws")
    if not isinstance(jws, str) or not jws.strip():
        return None, "attestation carries no jws"
    parts = jws.split(".")
    if len(parts) != 3:
        return None, f"jws is not a compact serialization ({len(parts)} parts)"
    if Ed25519PublicKey is None:
        return None, (
            "cryptography is not installed; detached Ed25519 JWS cannot be "
            "checked (pip install cryptography, or the [trust] extra)"
        )
    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        signature = _b64url_decode(parts[2])
    except (ValueError, UnicodeDecodeError) as exc:
        return None, f"jws does not decode: {exc}"
    if not isinstance(header, dict):
        return None, "jws header is not an object"
    if header.get("alg") not in ("EdDSA", "Ed25519"):
        return None, f"jws alg {header.get('alg')!r} is not Ed25519"

    kid = header.get("kid")
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list):
        return None, "jwks carries no keys array"
    # Candidates, not the first match. A JWKS legitimately holds an encryption
    # key beside a signing key, so taking the first kid-less entry could verify
    # against a key the issuer never meant for signatures; and trying only one
    # candidate turns a key rotation (old key still listed, signer's key second)
    # into a false SUSPECT. Absent `use`/`key_ops` means unrestricted. ora.ai's
    # live JWKS marks "use": "sig", so this filter costs nothing there.
    candidates = [
        k for k in keys
        if isinstance(k, dict)
        and k.get("kty") == "OKP"
        and k.get("crv") == "Ed25519"
        and (kid is None or k.get("kid") == kid)
        and k.get("use") in (None, "sig")
        and ("key_ops" not in k or "verify" in (k.get("key_ops") or []))
    ]
    if not candidates:
        return None, f"jwks has no Ed25519 signing key for kid {kid!r}"

    if parts[1]:
        # Attached payload: the signature covers what was served, verbatim -
        # which is exactly the trap. Callers read subject/issuer/issuedAt from
        # the OUTER object, so a genuine signature over an inner payload would
        # bless whatever claims were wrapped around it. The two must be the
        # same document, canonically, before the signature means anything.
        try:
            signed_body = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return None, f"attached jws payload does not decode: {exc}"
        if not isinstance(signed_body, dict) or (
            canonical_payload(signed_body) != canonical_payload(attestation)
        ):
            return False, "attached jws payload does not match the attestation"
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    else:
        signing_input = (
            f"{parts[0]}.{_b64url_encode(canonical_payload(attestation))}"
        ).encode("ascii")

    decoded = 0
    last = "jwk x does not decode"
    for key in candidates:
        try:
            public = Ed25519PublicKey.from_public_bytes(
                _b64url_decode(str(key.get("x", "")))
            )
        except (ValueError, TypeError) as exc:
            last = f"jwk x does not decode: {exc}"
            continue
        decoded += 1
        try:
            public.verify(signature, signing_input)
        except Exception:  # cryptography raises InvalidSignature, but a
            continue  # malformed key raises ValueError too
        return True, f"Ed25519 signature verified (kid {key.get('kid')!r})"
    if not decoded:
        return None, last
    return False, "signature did not verify"


def freshness(
    attestation: dict[str, Any], max_age_days: float
) -> tuple[bool | None, str]:
    """Check issuedAt/scannedAt against a maximum age.

    Returns (ok, detail); ok is None when no timestamp is present.
    """
    raw = attestation.get("issuedAt") or attestation.get("scannedAt")
    if not isinstance(raw, str):
        return None, "attestation carries no issuedAt/scannedAt"
    try:
        # fromisoformat on 3.10 does not accept a trailing Z.
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None, f"unparseable timestamp {raw!r}"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - stamp
    if age < -timedelta(days=1):
        # ponytail: one day of clock skew tolerated, because an issuer's clock
        # is not ours and a future stamp is otherwise indistinguishable from a
        # forged one. Ceiling: a genuinely pre-dated attestation passes.
        return False, f"issued {raw} is in the future"
    if age > timedelta(days=max_age_days):
        return False, f"issued {raw} is {age.days}d old, over {max_age_days}d"
    return True, f"issued {raw} ({age.days}d old)"


def verdict_entry(
    entry: dict[str, Any], hosted_from: str | None = None
) -> dict[str, Any]:
    """Assemble one entry's verdict.

    `hosted_from` is the domain the manifest was actually fetched from. It is
    the only offline-unforgeable evidence available: a file on disk can claim
    any identity, but a document served by ora.ai listing urn:air:ora.ai:...
    is hosted proof, which is what §4.5 asks a registry to check.
    """
    identifier = str(entry.get("identifier") or "")
    findings = screen_entry(entry)
    bound, identity, bind_findings = bind_identity(entry)
    findings.extend(bind_findings)

    hosted: bool | None = None
    authority = urn_authority(identifier)
    if hosted_from is not None:
        hosted = authority is not None and authority == hosted_from.lower()
        if not hosted:
            findings.append(
                f"manifest served by {hosted_from!r} lists a URN under "
                f"{authority!r}"
            )

    # An identity scheme this install cannot resolve is not an accusation: it is
    # a check we could not perform, and §4.5.1 explicitly allows SPIFFE and ANS
    # beside did:web. It used to be folded into `findings` first, which made the
    # UNSUPPORTED branch below unreachable and painted every spec-legal did:key
    # card as tampered. Worst still wins: any OTHER finding outranks it.
    unsupported = [f for f in bind_findings if f.startswith("identity scheme")]
    if [f for f in findings if f not in unsupported]:
        verdict = SUSPECT
    elif unsupported:
        verdict = UNSUPPORTED
    elif hosted and bound:
        verdict = VERIFIED
    elif identity is not None and bound:
        # Bound, but only by the entry's own text. The spec accepts a
        # cryptographic binding as sufficient, and this is not cryptographic.
        verdict = UNVERIFIED
        findings = [
            "identity is self-asserted; confirm hosting with --url "
            f"https://{authority}"
        ]
    else:
        verdict = UNVERIFIED
        if identity is None:
            findings = ["no trustManifest"]

    return {
        "identifier": identifier,
        "displayName": entry.get("displayName"),
        "verdict": verdict,
        "identity": identity,
        "bound": bound,
        "hosted": hosted,
        "findings": findings,
    }


def verdict_catalog(
    catalog: Any, hosted_from: str | None = None
) -> list[dict[str, Any]]:
    """Verdict every entry of a catalog document."""
    if not isinstance(catalog, dict):
        return []
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        return []
    return [
        verdict_entry(entry, hosted_from)
        for entry in entries
        if isinstance(entry, dict)
    ]


# Ceiling on any body read from a remote we do not control: this module's
# manifests and JWKS, and the registry's peer responses and inbound requests.
# A manifest is kilobytes (measured: ora.ai 2738, huggingface.co 701) and a
# search body is smaller still; an unbounded read() is an OOM lever.
# ponytail: one number for every untrusted read. Ceiling: a peer with a
# genuinely huge page. Upgrade path: paginate, or raise it here once.
MAX_BODY = 1_048_576


def fetch_json(url: str, timeout: float = 20.0) -> tuple[Any, str]:
    """GET one JSON document; returns (document, url-that-answered).

    The second element is the URL after redirects, which is not necessarily
    the URL that was asked. Raises OSError/ValueError like the rest.
    """
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "ard-verify"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_BODY + 1)
        final = response.geturl()
    if len(raw) > MAX_BODY:
        raise ValueError(f"{final} answered with more than {MAX_BODY} bytes")
    return json.loads(raw.decode("utf-8")), final


def fetch_manifest(base: str) -> tuple[Any, str, str]:
    """Fetch a registry manifest; returns (document, path-used, url-that-answered).

    Both spec paths are tried: v0.91 moved to ard.json and live registries
    disagree (measured 2026-09-04: ora.ai serves both, huggingface.co serves
    only the predecessor ai-catalog.json and 401s on ard.json).
    """
    root = base.rstrip("/")
    last: Exception | None = None
    for path in ("/.well-known/ard.json", "/.well-known/ai-catalog.json"):
        try:
            document, final = fetch_json(root + path)
            return document, path, final
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last = exc
    raise OSError(f"no manifest at {root}: {last}")


def host_of(base: str) -> str:
    """Domain of a base URL, lowercased, port stripped."""
    authority = re.sub(r"^https?://", "", base.rstrip("/")).split("/", 1)[0]
    return authority.split("@")[-1].split(":")[0].lower()


def summarize(verdicts: list[dict[str, Any]]) -> dict[str, int]:
    counts = {VERIFIED: 0, UNVERIFIED: 0, SUSPECT: 0, UNSUPPORTED: 0}
    for item in verdicts:
        counts[item["verdict"]] = counts.get(item["verdict"], 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 = nothing SUSPECT or UNSUPPORTED, 1 = either, 2 = cannot load."""
    parser = argparse.ArgumentParser(
        prog="ard-verify",
        description="Trust verdicts over ARD catalogs and attestations.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--catalog", help="Local ai-catalog.json to verify.")
    source.add_argument(
        "--url",
        help="Registry base URL; fetching the manifest from the claimed "
        "domain is itself the hosting evidence.",
    )
    source.add_argument(
        "--attestation", help="Attestation JSON carrying a detached jws."
    )
    parser.add_argument(
        "--jwks", help="JWKS URL or file for --attestation."
    )
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=90.0,
        help="Reject an attestation older than this (default 90).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable output."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only flagged rows (and the summary unless --json).",
    )
    args = parser.parse_args(argv)

    # A POSIX path would resolve under the system drive on Windows, and the
    # "cannot load catalog" line that follows would name a path nobody typed.
    path_error = guard_posix_paths({
        "catalog": args.catalog,
        "attestation": args.attestation,
        "jwks": args.jwks,
    })
    if path_error:
        print(f"ard-verify: {path_error}", file=sys.stderr)
        return 2

    if args.attestation:
        try:
            attestation = json.loads(
                Path(args.attestation).read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            print(f"ard-verify: cannot read attestation: {exc}", file=sys.stderr)
            return 2
        if not args.jwks:
            print("ard-verify: --attestation needs --jwks", file=sys.stderr)
            return 2
        try:
            jwks = (
                fetch_json(args.jwks)[0]
                if args.jwks.startswith(("http://", "https://"))
                else json.loads(Path(args.jwks).read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"ard-verify: cannot read jwks: {exc}", file=sys.stderr)
            return 2
        ok, detail = verify_jws(attestation, jwks)
        fresh_ok, fresh_detail = freshness(attestation, args.max_age_days)
        # None means "this check could not be performed" in both helpers, so
        # both must read as UNSUPPORTED. An undated attestation used to come
        # back VERIFIED forever, with --max-age-days silently inert. Worst
        # wins, so a failed signature stays SUSPECT even without a timestamp.
        verdict = (
            SUSPECT if ok is False or fresh_ok is False
            else UNSUPPORTED if ok is None or fresh_ok is None
            else VERIFIED
        )
        payload = {
            "verdict": verdict,
            "subject": attestation.get("subject"),
            "issuer": attestation.get("issuer"),
            "signature": detail,
            "freshness": fresh_detail,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"{verdict}  {payload['subject']}  {detail}  ({fresh_detail})")
        return 1 if verdict in _FLAGGED else 0

    if args.url and not args.url.startswith(("http://", "https://")):
        # Fetching the manifest from the claimed domain IS the hosting evidence
        # (spec 4.5). A local path proves nothing about any domain, and used to
        # come back VERIFIED with the URL scheme recorded as the "authority".
        print(
            "ard-verify: --url must be http(s); a local file is not hosting "
            "evidence (use --catalog)",
            file=sys.stderr,
        )
        return 2

    try:
        hosted_from: str | None = None
        if args.url:
            catalog, _path, final = fetch_manifest(args.url)
            # Credit the host that ANSWERED, not the one that was asked: a 302
            # to another domain used to be recorded as hosting evidence for the
            # requested name, which made a redirect a VERIFIED forge.
            hosted_from = host_of(final)
            if not args.json:
                print(f"# manifest {final}", file=sys.stderr)
        else:
            catalog = json.loads(
                Path(args.catalog).read_text(encoding="utf-8")
            )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"ard-verify: cannot load catalog: {exc}", file=sys.stderr)
        return 2

    verdicts = verdict_catalog(catalog, hosted_from)
    if not verdicts:
        print("ard-verify: no entries found in catalog", file=sys.stderr)
        return 2
    counts = summarize(verdicts)

    if args.json:
        print(
            json.dumps(
                {
                    "source": args.url or args.catalog,
                    "hostedFrom": hosted_from,
                    "counts": counts,
                    "verdicts": [
                        v for v in verdicts
                        if not args.quiet or v["verdict"] in _FLAGGED
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for item in verdicts:
            if args.quiet and item["verdict"] not in _FLAGGED:
                continue
            line = f"{item['verdict']:<11} {item['identifier']}"
            print(line)
            for finding in item["findings"]:
                print(f"            - {finding}")
        order = (VERIFIED, SUSPECT, UNSUPPORTED, UNVERIFIED)
        total = ", ".join(f"{name} {counts[name]}" for name in order)
        print(f"# {len(verdicts)} entries: {total}")
    return 1 if counts[SUSPECT] + counts[UNSUPPORTED] else 0


if __name__ == "__main__":
    sys.exit(main())
