# Troubleshooting Guide

## Common Issues and Solutions

### Slow Page Loads (15-20 seconds)

**Symptoms:**
- First page load is fast
- Navigating to another page is very slow
- Reloading the same page is fast
- `/health` endpoint is slow after using the app

**Root Cause:** Server-Sent Events (SSE) blocking the single worker

The SSE endpoint `/sse/round/<id>` maintains a long-lived connection for live updates. On single-worker deployments (PythonAnywhere free tier, Railway free tier), this connection blocks the only available worker, making all other requests wait.

**Solution:** Set environment variable `DISABLE_SSE=1`

- **Railway:** Variables tab → Add `DISABLE_SSE` = `1`
- **PythonAnywhere:** Add to WSGI config file:
  ```python
  import os
  os.environ['DISABLE_SSE'] = '1'
  ```

**Trade-off:** Live score updates won't work automatically. Users need to manually refresh to see updates.

---

### Worker Timeout on Railway

**Symptoms:**
```
[CRITICAL] WORKER TIMEOUT (pid:X)
Worker exiting (pid: X)
```

**Causes:**
1. Database initialization too slow (volume mount latency)
2. SSE holding worker (see above)

**Solutions:**
1. Set `SKIP_MIGRATIONS=1` to skip DB migrations on startup
2. Set `DISABLE_SSE=1` to prevent SSE blocking
3. Procfile uses `--preload` and `--timeout 300` for resilience

---

### Safari CSRF/Login Issues

**Symptoms:**
- Login works on Chrome but not Safari
- CSRF token errors on Safari
- Session not persisting on Safari

**Root Cause:** `SESSION_COOKIE_SECURE=True` blocks cookies on HTTP (localhost)

**Solution:** Run local development with `FLASK_DEBUG=1`:
```bash
FLASK_DEBUG=1 python app.py
```

---

### "Tallenna" Button Not Working

**Symptoms:**
- Clicking save/submit buttons does nothing
- No error in UI, but action doesn't complete

**Root Cause:** Content Security Policy (CSP) blocks inline `onclick` handlers

**Solution:** Use `addEventListener` instead of inline `onclick`:
```javascript
// Bad (blocked by CSP)
<button onclick="doSomething()">

// Good (CSP compliant)
<button id="myBtn">
<script>
document.getElementById('myBtn').addEventListener('click', doSomething);
</script>
```

---

### Database Locked Errors

**Symptoms:**
- `database is locked` errors
- Slow queries after writes

**Solutions implemented:**
1. SQLite timeout set to 10 seconds: `sqlite3.connect(path, timeout=10.0)`
2. WAL mode enabled in `init_db()`: `PRAGMA journal_mode=WAL`
3. Connections properly closed via `@app.teardown_appcontext`

---

## Environment Variables Reference

| Variable | Purpose | Platforms |
|----------|---------|-----------|
| `DISABLE_SSE=1` | Disable Server-Sent Events | Railway, PythonAnywhere |
| `SKIP_MIGRATIONS=1` | Skip DB migrations on startup | Railway |
| `DATABASE_PATH` | Custom database file location | Railway (`/data/padel.db`) |
| `SECRET_KEY` | Flask session encryption | All |
| `ADMIN_SETUP_TOKEN` | Initial admin setup | All |

---

## Debugging Tips

### Enable Request Timing Logs

The app logs request timing when running:
```
[REQ START] GET /tournament/1
[REQ END] GET /tournament/1 - 0.056s - 200
```

Check server logs for slow requests.

### Health Check Endpoints

- `/health` - Basic health (no DB)
- `/health/db` - Health with DB query timing

Use these to isolate if slowness is infrastructure or code.

