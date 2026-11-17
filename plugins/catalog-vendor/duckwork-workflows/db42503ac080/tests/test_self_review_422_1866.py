#!/usr/bin/env python3
"""est-2ek.1.866 — the formal-review step is AUTHOR-AWARE (RED on base, GREEN on branch).

Field evidence: duckwork-workflows#245 reconcile tried the formal REQUEST_CHANGES
review as the shared credential WHO IS ALSO the PR author — the POST answered
HTTP 422 with the verbatim errors text "Can not request changes on your own
pull request" (receipt: the ra-pr-deep reconcile work dir, review-refused.json,
PR at e08513f8a5ed2fd325f0d5c5afc9d18bf9d1bebf). The verified fallback that DID
land the verdict on #245: the live marker comment 6019510641 PATCHed + the
`changes-requested` label, both read back — and no merge happened.

Pinned law (scripts/pr_formal_review.py), against a STATEFUL fake GitHub:
  T1  self-review detected BEFORE posting (credential login == PR author):
      the doomed POST /reviews is NEVER attempted; the fallback runs and records
      its reason, the repo-admin marker stays the comment's LAST line, the label
      is ADDED (POST issues/{n}/labels) — every pre-existing label survives
      (never the replace-all `PATCH issues/{n} {labels}`); verified ONLY by
      read-backs (GET the comment + GET the labels).
  T2  clean preflight (different identities) -> the formal review POSTs and no
      fallback artifacts are written.
  T3  the 422 shape itself mocked (defense in depth): preflight clean but the
      POST still returns 422 -> the same fallback, reason recorded.
  T4  a fallback write that does NOT land (read-back disproves it) claims
      verified=False (loud, never silent).
  T5  no identity is ever forged: every call rides the ONE token passed in.
  T6  law 3 (one live comment per PR): given the live marker comment id, the
      fallback PATCHes THAT comment — no second comment is created.
Stdlib only; the network never runs — the transport seam is the fake.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pr_formal_review.py"

spec = importlib.util.spec_from_file_location("_self_review_1866", SCRIPT)
fails = 0


def check(label, cond, detail: object = ""):
    global fails
    print(("PASS " if cond else "FAIL ") + label +
          (f"  {str(detail)[:400]}" if detail and not cond else ""))
    if not cond:
        fails += 1


if spec is None:
    check("scripts/pr_formal_review.py exists", False, str(SCRIPT))
    print("DONE self_review_422_1866 FAIL")
    sys.exit(1)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as exc:
    check("module loads", False, f"{type(exc).__name__}: {exc}")
    print("DONE self_review_422_1866 FAIL")
    sys.exit(1)

REPO = "octocat/whatever"
PR = 245
LIVE = 6019510641
FALLBACK_MARK = "repo-admin formal-review-fallback"
RA_MARK = "<!-- repo-admin reviewed=e08513f verdict=changes profile=bot reviewer=peer-bot -->"
BODY = "FINDINGS: request changes.\n\n" + RA_MARK + "\n"

# the #245 field receipt, verbatim shape
HTTP_422_SELF_REVIEW = (422, {"message": "Unprocessable Entity",
                              "errors": ["Review Can not request changes on your own pull request"],
                              "documentation_url": "https://docs.github.com/rest/pulls/reviews",
                              "status": "422"})


class FakeGitHub:
    """Stateful transport: comments and labels persist across calls, and the
    replace-all `PATCH issues/{n} {labels}` is modelled faithfully (it WIPES
    every label not in the list). drop=True accepts writes but never lands them."""

    def __init__(self, me="estate-cred", author="estate-cred", review=None,
                 labels=("keep-me",), comments=None, drop=False):
        self.calls = []
        self.me, self.author, self.review = me, author, review
        self.labels = list(labels)
        self.comments = dict(comments or {})
        self.next_id = 7000
        self.drop = drop

    def _labels(self):
        return [{"name": n} for n in self.labels]

    def __call__(self, method, url, body, token):
        self.calls.append((method, url, body, token))
        p = url.replace(mod.API, "")
        base = f"/repos/{REPO}"
        if method == "GET" and p == "/user":
            return 200, {"login": self.me}
        if method == "GET" and p == f"{base}/pulls/{PR}":
            return 200, {"user": {"login": self.author}, "labels": self._labels()}
        if method == "POST" and p == f"{base}/pulls/{PR}/reviews":
            if self.review is None:
                raise AssertionError("review POST not expected here")
            return self.review
        if method == "POST" and p == f"{base}/issues/{PR}/comments":
            self.next_id += 1
            if not self.drop:
                self.comments[self.next_id] = body["body"]
            return 201, {"id": self.next_id}
        if p.startswith(f"{base}/issues/comments/"):
            cid = int(p.rsplit("/", 1)[1])
            if cid not in self.comments:
                return 404, {"message": "Not Found"}
            if method == "PATCH":
                if not self.drop:
                    self.comments[cid] = body["body"]
                return 200, {"id": cid}
            if method == "GET":
                return 200, {"id": cid, "body": self.comments[cid]}
        if method == "POST" and p == f"{base}/issues/{PR}/labels":
            if not self.drop:
                for n in body["labels"]:
                    if n not in self.labels:
                        self.labels.append(n)
            return 200, self._labels()
        if method == "GET" and p == f"{base}/issues/{PR}/labels":
            return 200, self._labels()
        if method == "PATCH" and p == f"{base}/issues/{PR}":
            if "labels" in (body or {}):
                self.labels = list(body["labels"])          # GitHub: REPLACE-ALL
            return 200, {}
        raise AssertionError(f"unexpected call {method} {url}")

    def posted_reviews(self):
        return [c for c in self.calls if c[0] == "POST" and c[1].endswith("/reviews")]

    def new_comments(self):
        return [c for c in self.calls if c[0] == "POST" and c[1].endswith(f"/issues/{PR}/comments")]


# ---- T1: self-review preflight -> doomed POST NEVER attempted, fallback verified
g = FakeGitHub()
out = mod.post_formal_review(REPO, PR, BODY, token="t0ken", transport=g)
check("T1 self-review detected BEFORE posting (credential == author recorded)",
      out.get("self_review", {}).get("self_review") is True
      and out["self_review"].get("credential") == "estate-cred"
      and out["self_review"].get("author") == "estate-cred", out.get("self_review"))
check("T1 the doomed POST /reviews is NEVER attempted", g.posted_reviews() == [],
      g.posted_reviews())
written = list(g.comments.values())
check("T1 fallback comment records the fallback reason",
      len(written) == 1 and FALLBACK_MARK in written[0] and "self-review" in written[0],
      written)
check("T1 the repo-admin marker stays the comment's LAST line (marker law)",
      len(written) == 1 and written[0].rstrip().splitlines()[-1] == RA_MARK,
      written[0][-300:] if written else written)
check("T1 changes-requested ADDED and every pre-existing label survives (no replace-all)",
      "changes-requested" in g.labels and "keep-me" in g.labels
      and not any(c[0] == "PATCH" and c[1].endswith(f"/issues/{PR}") for c in g.calls),
      (g.labels, [(c[0], c[1]) for c in g.calls if c[0] != "GET"]))
check("T1 fallback verified by READ-BACK (comment GET + labels GET)",
      out.get("posted") == "fallback" and out.get("verified") is True
      and out.get("fallback_used") == "self-review-preflight"
      and any(c[0] == "GET" and "/issues/comments/" in c[1] for c in g.calls)
      and any(c[0] == "GET" and c[1].endswith(f"/issues/{PR}/labels") for c in g.calls), out)

# ---- T2: clean preflight -> formal review posts, zero fallback artifacts
g2 = FakeGitHub(author="contributor-x", review=(200, {"id": 42}))
out2 = mod.post_formal_review(REPO, PR, BODY, token="t0ken", transport=g2)
check("T2 different identities: the formal REQUEST_CHANGES review POSTs",
      out2.get("posted") == "review" and out2.get("verified") is True
      and len(g2.posted_reviews()) == 1
      and g2.posted_reviews()[0][2].get("event") == "REQUEST_CHANGES", out2)
check("T2 no fallback writes when the review landed",
      not any(c[0] in ("POST", "PATCH") and "/issues/" in c[1] for c in g2.calls),
      [(c[0], c[1]) for c in g2.calls])

# ---- T3: the 422 field shape mocked — preflight clean, POST refuses -> fallback
g3 = FakeGitHub(author="contributor-x", review=HTTP_422_SELF_REVIEW)
out3 = mod.post_formal_review(REPO, PR, BODY, token="t0ken", transport=g3)
check("T3 mocked 422 (GitHub refuses the review): fallback taken and verified",
      out3.get("posted") == "fallback" and out3.get("verified") is True
      and out3.get("fallback_used") == "post-422-self-review"
      and "keep-me" in g3.labels and "changes-requested" in g3.labels, out3)

# ---- T4: writes accepted but never landed -> verified=False, loud
g4 = FakeGitHub(drop=True)
out4 = mod.post_formal_review(REPO, PR, BODY, token="t0ken", transport=g4)
check("T4 fallback write not proven by read-back -> verified False (never silent)",
      out4.get("posted") == "fallback" and out4.get("verified") is False, out4)

# ---- T5: one credential, never forged
check("T5 every API call rides the ONE passed token (no forged identity)",
      all(c[3] == "t0ken" for c in g.calls + g2.calls + g3.calls + g4.calls))

# ---- T6: law 3 — the live marker comment is PATCHed, never duplicated
g6 = FakeGitHub(comments={LIVE: "old findings\n\n" + RA_MARK + "\n"})
out6 = mod.post_formal_review(REPO, PR, BODY, token="t0ken", transport=g6, comment_id=LIVE)
check("T6 live comment id given: that comment is PATCHed, NO second comment created",
      g6.new_comments() == [] and len(g6.comments) == 1
      and FALLBACK_MARK in g6.comments[LIVE]
      and g6.comments[LIVE].rstrip().splitlines()[-1] == RA_MARK, g6.comments)
check("T6 verified by read-back of the live comment",
      out6.get("verified") is True and out6.get("receipts", {}).get("fallback", {})
      .get("comment_id") == LIVE, out6)

print("DONE self_review_422_1866", "OK" if fails == 0 else "FAIL")
sys.exit(0 if fails == 0 else 1)
