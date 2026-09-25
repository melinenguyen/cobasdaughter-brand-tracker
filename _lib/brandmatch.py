#!/usr/bin/env python3
"""
Typo-tolerant brand matching for the mention alarm.

The brand gets written every possible way in the wild — #cobasdaughter, #CoBasDaughter,
#cobadaughter, #cobasdaugther, "CoBa's Daughter", "Cobas Daughter", "coba daughter".
Exact matching misses most of that, so everything is normalised to a bare alphanumeric
form and compared with bounded edit distance.

Normalisation: lowercase, strip everything that isn't a-z0-9.
  "#CoBa's Daughter" -> "cobasdaughter"
  "Coba Daughter"    -> "cobadaughter"   (distance 1 from canonical)
  "cobasdaugther"    -> transposition    (distance 2)

Why distance ≤2 is safe here: "cobasdaughter" is a distinctive 13-character string.
Nothing in ordinary English lands within 2 edits of it, so false positives are
effectively nil — verified against a deliberately adversarial list in self-test.

  python3 _system/brandmatch.py        # run the self-test
"""
import re

CANON = "cobasdaughter"
# Distinct enough to be safe at distance 2; short forms get a tighter budget.
MAX_DIST = 2
ALNUM = re.compile(r"[^a-z0-9]+")


def norm(s):
    return ALNUM.sub("", (s or "").lower())


def edit_distance(a, b, cap):
    """
    Damerau-Levenshtein with early exit — transpositions cost 1, not 2, because
    swapping two letters ("daugther") is one of the commonest ways people mistype
    this name. Returns cap+1 once it's certainly over budget.
    """
    la, lb = len(a), len(b)
    if abs(la - lb) > cap:
        return cap + 1
    prev2 = None
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [cap + 1] * lb
        lo, hi = max(1, i - cap), min(lb, i + cap)
        for j in range(lo, hi + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (a[i - 1] != b[j - 1]))
            if (prev2 is not None and i > 1 and j > 1
                    and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]):
                cur[j] = min(cur[j], prev2[j - 2] + 1)      # transposition
        if min(cur[lo:hi + 1] or [cap + 1]) > cap:
            return cap + 1
        prev2, prev = prev, cur
    return prev[lb]


def _budget(token):
    """Short tokens get a tighter budget so 'coba' alone can't match."""
    n = len(token)
    if n < 8:
        return 0
    return 1 if n < 11 else MAX_DIST


def matches_token(token):
    """Is this single token (a hashtag or handle) the brand, typos allowed?"""
    t = norm(token)
    if not t:
        return False
    if t.startswith(CANON):          # #cobasdaughterpartner, #cobasdaughterusa …
        return True
    return edit_distance(t, CANON, _budget(t)) <= _budget(t)


def find_in_text(text):
    """
    Is the brand named anywhere in free text, typos allowed?

    Works on the normalised string so word spacing and punctuation stop mattering,
    then slides a window only where it could plausibly start (an anchor of 'cob' or
    'oba'), which keeps this cheap on long captions.
    """
    s = norm(text)
    if not s:
        return False
    if CANON in s:
        return True
    L = len(CANON)
    anchors = {m.start() for m in re.finditer(r"cob|oba|kob", s)}
    # Try a few start offsets, not just one: the anchor may sit at the brand's first
    # letter or a letter or two in, and starting even one char early misaligns the
    # comparison enough to blow the distance budget.
    for i in sorted(anchors):
        for start in (i, i - 1, i - 2):
            if start < 0:
                continue
            for w in (L - 2, L - 1, L, L + 1, L + 2):
                seg = s[start:start + w]
                if len(seg) >= L - 2 and edit_distance(seg, CANON, MAX_DIST) <= MAX_DIST:
                    return True
    return False


def matches(text=None, tokens=None):
    """Convenience: true if the brand appears in the text OR in any token."""
    if text and find_in_text(text):
        return True
    return any(matches_token(t) for t in (tokens or []))


if __name__ == "__main__":
    SHOULD_HIT = [
        "#cobasdaughter", "#CoBasDaughter", "#Cobasdaughter", "#cobadaughter",
        "#cobasdaugther", "#cobasdaughters", "#cobasdaughterpartner",
        "#cobasdaughterusa", "#CoBaSDaughter", "cobasdaughter.official",
    ]
    TEXT_HIT = [
        "love this @cobasdaughter scrub", "CoBa's Daughter is amazing",
        "Coba Daughter body scrub", "cobas daughter review", "COBA'S DAUGHTER",
        "trying Coba’s Daughter tonight", "cobasdaugther haul",
        "the CoBa Daughter coffee scrub", "obsessed with Cobas-Daughter",
    ]
    SHOULD_MISS = [
        "#coffee", "#daughter", "#coba", "#mydaughter", "#cocoabutter",
        "#coffeescrub", "#bodyscrub", "#skincare", "#vietnam", "#cosrx",
        "#daughtersofthesun", "#cobalt", "#cobaltblue", "#cocobeauty",
    ]
    TEXT_MISS = [
        "my daughter loves coffee", "cobalt blue nails", "cocoa butter daughter",
        "coba is a city in mexico", "best coffee scrub ever",
    ]
    fails = 0
    for t in SHOULD_HIT:
        if not matches_token(t):
            print(f"  MISS (should hit): {t}"); fails += 1
    for t in TEXT_HIT:
        if not find_in_text(t):
            print(f"  MISS (should hit): {t!r}"); fails += 1
    for t in SHOULD_MISS:
        if matches_token(t):
            print(f"  FALSE POSITIVE: {t}"); fails += 1
    for t in TEXT_MISS:
        if find_in_text(t):
            print(f"  FALSE POSITIVE: {t!r}"); fails += 1
    total = len(SHOULD_HIT) + len(TEXT_HIT) + len(SHOULD_MISS) + len(TEXT_MISS)
    print(f"self-test: {total - fails}/{total} passed" + ("" if fails else "  ✓ all good"))
