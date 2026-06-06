"""Login / logout routes for the dashboard."""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from cryptoswarm.api.auth import (
    make_session_token, verify_session_token,
    check_password, _SESSION_COOKIE, _SESSION_MAX_AGE,
)

router = APIRouter()

_LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CryptoSwarm — Login</title>
<style>
:root{--bg:#090e14;--s1:#0d1420;--s2:#111927;--b1:#1e2d42;--t1:#e8f0fe;--t2:#94a3b8;--gr:#00d084;--re:#ff4757;--bl:#3d8bff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--t1);font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:var(--s1);border:1px solid var(--b1);border-radius:16px;padding:40px;width:380px;box-shadow:0 25px 60px rgba(0,0,0,.5)}
.logo{text-align:center;margin-bottom:32px}
.logo-icon{width:56px;height:56px;background:linear-gradient(135deg,#3d8bff,#a78bfa);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:28px;margin:0 auto 12px}
.logo h1{font-size:20px;font-weight:700}
.logo p{font-size:13px;color:var(--t2);margin-top:4px}
.field{margin-bottom:16px}
label{display:block;font-size:12px;font-weight:500;color:var(--t2);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em}
input{width:100%;background:var(--s2);border:1px solid var(--b1);border-radius:8px;padding:11px 14px;font-size:14px;color:var(--t1);outline:none;transition:border-color .2s}
input:focus{border-color:var(--bl)}
.btn{width:100%;background:var(--bl);color:#fff;border:none;border-radius:8px;padding:12px;font-size:14px;font-weight:600;cursor:pointer;margin-top:8px;transition:background .2s}
.btn:hover{background:#1a6bdd}
.error{background:rgba(255,71,87,.1);border:1px solid rgba(255,71,87,.2);border-radius:8px;padding:10px 14px;font-size:13px;color:var(--re);margin-bottom:16px;display:none}
.error.show{display:block}
.footer{text-align:center;margin-top:24px;font-size:12px;color:var(--t2)}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <h1>CryptoSwarm</h1>
    <p>AI Trading Dashboard</p>
  </div>
  <div class="error{err_class}" id="err">{err_msg}</div>
  <form method="POST" action="/login">
    <div class="field">
      <label>Username</label>
      <input type="text" name="username" placeholder="Enter username" autocomplete="username" required autofocus>
    </div>
    <div class="field">
      <label>Password</label>
      <input type="password" name="password" placeholder="Enter password" autocomplete="current-password" required>
    </div>
    <button type="submit" class="btn">Sign In</button>
  </form>
  <div class="footer">Paper Trading Mode · No real funds at risk</div>
</div>
</body>
</html>"""


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    err_class = " show" if error else ""
    err_msg = error if error else ""
    return _LOGIN_HTML.replace("{err_class}", err_class).replace("{err_msg}", err_msg)


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    from cryptoswarm.config.settings import get_settings
    cfg = get_settings()

    if username != cfg.dashboard_username or not check_password(password, cfg.dashboard_password):
        return HTMLResponse(
            _LOGIN_HTML
            .replace("{err_class}", " show")
            .replace("{err_msg}", "Invalid username or password"),
            status_code=401,
        )

    token = make_session_token(username, cfg.dashboard_secret_key)
    resp = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie(
        key=_SESSION_COOKIE,
        value=token,
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(_SESSION_COOKIE)
    return resp
