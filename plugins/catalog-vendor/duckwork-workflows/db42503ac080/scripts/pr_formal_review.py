#!/usr/bin/env python3
"""pr_formal_review.py — the AUTHOR-AWARE formal-review step (est-2ek.1.866).

The ra-pr-deep reconcile lane must post a formal REQUEST_CHANGES review, but the
shared GitHub credential is the PR author for the estate's own PRs:
`POST /repos/{repo}/pulls/{n}/reviews` with event=REQUEST_CHANGES then answers
HTTP 422 ("Can not request changes on your own pull request" — field receipt:
duckwork-workflows#245 @ e08513f8, the reconcile node's review-refused.json).

The verified fallback (proven live on #245: live marker comment 6019510641 +
the `changes-requested` label, both read back):
  1. detect self-review BEFORE posting — compare the credential login
     (GET /user) with the PR author (GET pulls/{n}); never forge an identity;
  2. skip the doomed POST when they match;
  3. write the findings to the ONE live marker comment (law 3: PATCH it when
     --comment-id is given, else create it), with a
     `formal-review-fallback=<reason>` record inserted BEFORE the trailing
     repo-admin marker (the marker stays the comment's last line);
  4. ADD the `changes-requested` label (POST issues/{n}/labels — never the
     replace-all `PATCH issues/{n} {labels}`, which wipes every other label);
  5. READ BOTH back (GET the comment itself + GET the label list) — no
     read-back, no claim;
  6. if the preflight says clean but the POST still answers 422, take the same
     fallback (defense in depth).

Exit codes: 0 = review posted OR fallback fully verified; 1 = fallback not
proven by read-back (loud, never silent); 2 = review POST failed otherwise.
Usage:
  GITHUB_TOKEN=... python3 scripts/pr_formal_review.py --repo owner/name --pr N \\
      --body-file findings.md [--comment-id LIVE_MARKER_COMMENT_ID] [--event REQUEST_CHANGES]
Stdlib only; the transport is one seam (`_transport`) so tests fake GitHub
without the network. The token is read from GITHUB_TOKEN and NEVER printed.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
LABEL = "changes-requested"
RA_MARKER = "<!-- repo-admin reviewed="


def _transport(method, url, body, token):
    """The ONE network seam: tests replace it with a fake.
    Returns (status:int, parsed_json_or_{})."""
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "duckwork-repo-admin-formal-review"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read())
        except Exception:
            payload = {}
        return e.code, payload


def _ok(st):
    return 200 <= st < 300


def self_review_state(repo, pr, token, transport=_transport):
    """Compare credential login vs PR author BEFORE posting (law: detect,
    skip, fallback — never attempt-and-hope, never forge an identity)."""
    st_me, me = transport("GET", API + "/user", None, token)
    st_pr, pull = transport("GET", f"{API}/repos/{repo}/pulls/{pr}", None, token)
    login = str((me or {}).get("login") or "") if _ok(st_me) else ""
    author = str(((pull or {}).get("user") or {}).get("login") or "") if _ok(st_pr) else ""
    return {"credential": login, "author": author,
            "self_review": bool(login and author and login.lower() == author.lower())}


def _mark(body, reason):
    """Insert the fallback record BEFORE the trailing repo-admin marker so the
    marker stays the comment's last line (marker law); append when absent."""
    record = (f"_Formal review not possible: {reason} (the posting credential is "
              f"the PR author). Verdict carried by this comment + the `{LABEL}` "
              f"label._\n<!-- repo-admin formal-review-fallback={reason} -->\n")
    text = body.rstrip() + "\n"
    i = text.rfind(RA_MARKER)
    if i == -1:
        return text + "\n" + record
    return text[:i] + record + text[i:]


def _fallback(repo, pr, body, token, transport, reason, receipts, comment_id=None):
    marked = _mark(body, reason)
    if comment_id:
        st_c, c = transport("PATCH", f"{API}/repos/{repo}/issues/comments/{comment_id}",
                            {"body": marked}, token)
    else:
        st_c, c = transport("POST", f"{API}/repos/{repo}/issues/{pr}/comments",
                            {"body": marked}, token)
    cid = (c or {}).get("id") if _ok(st_c) else None
    st_l, _ = transport("POST", f"{API}/repos/{repo}/issues/{pr}/labels",
                        {"labels": [LABEL]}, token)
    # read-backs: a write is only CLAIMED once a GET proves it landed
    rb_body = ""
    if cid is not None:
        st_rb, rb = transport("GET", f"{API}/repos/{repo}/issues/comments/{cid}", None, token)
        rb_body = str((rb or {}).get("body") or "") if _ok(st_rb) else ""
    st_lb, lb = transport("GET", f"{API}/repos/{repo}/issues/{pr}/labels", None, token)
    labels = [str((x or {}).get("name")) for x in lb] if _ok(st_lb) and isinstance(lb, list) else []
    comment_ok = f"formal-review-fallback={reason}" in rb_body
    verified = comment_ok and LABEL in labels
    receipts["fallback"] = {"reason": reason, "comment_id": cid,
                            "comment_write": "PATCH" if comment_id else "POST",
                            "comment_write_status": st_c, "label_status": st_l,
                            "comment_readback": comment_ok, "labels_readback": labels,
                            "verified": verified}
    return {"posted": "fallback", "fallback_used": reason, "verified": verified,
            "self_review": receipts.get("self_review"), "receipts": receipts}


def post_formal_review(repo, pr, body, event="REQUEST_CHANGES", token=None,
                       transport=_transport, comment_id=None):
    """Author-aware formal review. Returns a verdict dict; the CLI exits
    non-zero when `verified` is False (loud, never silent)."""
    token = token or os.environ.get("GITHUB_TOKEN") or ""
    receipts = {}
    ss = self_review_state(repo, pr, token, transport)
    receipts["self_review"] = ss
    if ss["self_review"]:
        # The doomed POST is NEVER attempted (the 422 is known a priori).
        return _fallback(repo, pr, body, token, transport, "self-review-preflight",
                         receipts, comment_id)
    st, rev = transport("POST", f"{API}/repos/{repo}/pulls/{pr}/reviews",
                        {"body": body, "event": event}, token)
    if st == 422:
        receipts["review_attempt"] = {"status": st, "body": rev}
        return _fallback(repo, pr, body, token, transport, "post-422-self-review",
                         receipts, comment_id)
    if _ok(st):
        return {"posted": "review", "fallback_used": None, "verified": True,
                "review_id": (rev or {}).get("id"), "self_review": ss,
                "receipts": receipts}
    receipts["review_attempt"] = {"status": st, "body": rev}
    return {"posted": "failed", "fallback_used": None, "verified": False,
            "self_review": ss, "receipts": receipts}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Author-aware formal PR review (est-2ek.1.866)")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--comment-id", type=int, default=None,
                    help="the live repo-admin marker comment to PATCH (law 3)")
    ap.add_argument("--event", default="REQUEST_CHANGES")
    a = ap.parse_args(argv)
    with open(a.body_file, encoding="utf-8") as f:
        body = f.read()
    out = post_formal_review(a.repo, a.pr, body, event=a.event, comment_id=a.comment_id)
    print(json.dumps(out, indent=2, default=str)[:6000])
    if out["verified"]:
        return 0
    return 1 if out["posted"] == "fallback" else 2


if __name__ == "__main__":
    sys.exit(main())
