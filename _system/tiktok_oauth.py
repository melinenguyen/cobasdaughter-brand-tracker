#!/usr/bin/env python3
"""
One-time OAuth setup for the official TikTok Display API (own-account stats).

  python3 _system/tiktok_oauth.py --auth-url REDIRECT_URI
      -> prints the URL to open in a browser, logged in as @cobasdaughter.official

  python3 _system/tiktok_oauth.py --exchange CODE REDIRECT_URI
      -> exchanges the code from the redirect for an access + refresh token,
         stores both in _system/.tiktok_env

Needs TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET already in _system/.tiktok_env.
"""
import os, sys, json, secrets, hashlib, base64, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SCOPES = "user.info.basic,user.info.stats,video.list"  # stats scope needed for follower/likes/video counts
PKCE_FILE = os.path.join(HERE, ".tiktok_pkce")  # transient, gitignored — holds the verifier between auth-url and exchange


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _envfile(key):
    p = os.path.join(HERE, ".tiktok_env")
    if os.path.exists(p):
        for ln in open(p):
            if ln.strip().startswith(key + "="):
                return ln.split("=", 1)[1].strip()
    return ""


def creds():
    return (os.environ.get("TIKTOK_CLIENT_KEY", "").strip() or _envfile("TIKTOK_CLIENT_KEY"),
            os.environ.get("TIKTOK_CLIENT_SECRET", "").strip() or _envfile("TIKTOK_CLIENT_SECRET"))


def auth_url(redirect_uri):
    key, _ = creds()
    state = secrets.token_hex(8)
    verifier = _b64url(secrets.token_bytes(64))          # 43-128 char url-safe string, per RFC 7636
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    open(PKCE_FILE, "w").write(verifier)
    q = urllib.parse.urlencode({
        "client_key": key, "scope": SCOPES, "response_type": "code",
        "redirect_uri": redirect_uri, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    return f"https://www.tiktok.com/v2/auth/authorize/?{q}", state


def exchange(code, redirect_uri):
    key, secret = creds()
    verifier = open(PKCE_FILE).read().strip() if os.path.exists(PKCE_FILE) else ""
    data = urllib.parse.urlencode({
        "client_key": key, "client_secret": secret, "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }).encode()
    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/oauth/token/", data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def refresh():
    """Access token dies in 24h; refresh token lasts a year. Call this before
    every use rather than tracking expiry — refreshing early is free and safe."""
    key, secret = creds()
    refresh_token = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip() or _envfile("TIKTOK_REFRESH_TOKEN")
    if not refresh_token:
        return None
    data = urllib.parse.urlencode({
        "client_key": key, "client_secret": secret,
        "grant_type": "refresh_token", "refresh_token": refresh_token,
    }).encode()
    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/oauth/token/", data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode())
    if "access_token" in resp:
        store(resp)
        return resp["access_token"]
    return None


def revoke():
    """Invalidates whatever access/refresh token is currently stored — used
    when a token has leaked (e.g. printed somewhere it shouldn't have been)."""
    key, secret = creds()
    tok = os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip() or _envfile("TIKTOK_ACCESS_TOKEN")
    if not tok:
        return False
    data = urllib.parse.urlencode({"client_key": key, "client_secret": secret, "token": tok}).encode()
    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/oauth/revoke/", data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode())
    return resp.get("error", {}).get("code") == "ok"


def store(resp):
    p = os.path.join(HERE, ".tiktok_env")
    lines = [ln for ln in (open(p).read().splitlines() if os.path.exists(p) else [])
             if not ln.startswith(("TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN", "TIKTOK_OPEN_ID"))]
    lines += [
        f"TIKTOK_ACCESS_TOKEN={resp['access_token']}",
        f"TIKTOK_REFRESH_TOKEN={resp['refresh_token']}",
        f"TIKTOK_OPEN_ID={resp.get('open_id', '')}",
    ]
    open(p, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--auth-url"]:
        url, state = auth_url(args[1])
        print(f"Open this URL, log in as @cobasdaughter.official, approve, then copy the\n"
              f"'code' param from wherever it redirects you (state should echo back {state}):\n\n{url}\n")
    elif args[:1] == ["--revoke"]:
        print("✓ revoked" if revoke() else "✗ revoke failed (token may already be invalid, which is fine)")
    elif args[:1] == ["--exchange"]:
        code, redirect_uri = args[1], args[2]
        resp = exchange(code, redirect_uri)
        if "access_token" in resp:
            store(resp)
            print(f"✓ stored. scopes granted: {resp.get('scope')}, "
                  f"expires_in: {resp.get('expires_in')}s, refresh_expires_in: {resp.get('refresh_expires_in')}s")
        else:
            print("✗ exchange failed:", json.dumps(resp, indent=2))
    else:
        print(__doc__)
