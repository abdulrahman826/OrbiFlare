# Deploying OrbiFlare

Backend (FastAPI) on Render, frontend (Next.js) on Vercel.

## 1. Rotate the NASA MAP_KEY first
The key used during development was exposed and must be treated as compromised. Request a new one at
https://firms.modaps.eosdis.nasa.gov/api/map_key/ and use only the new key below.

## 2. Backend on Render
1. Render dashboard -> New -> Blueprint -> connect this GitHub repo (it reads `render.yaml`).
2. Set the secret env vars when prompted: `FIRMS_MAP_KEY` (new key) and `CORS_ORIGINS` (your Vercel URL; you can edit it after step 3).
3. Deploy. Check `https://<service>.onrender.com/api/health` -> `"status":"ok"`.
   On first start the API pulls live FIRMS data in the background (a few minutes) and builds events from it.

Notes: the database is a SQLite file on the container's disk (ephemeral): every restart/redeploy rebuilds it from a fresh FIRMS
sync (last ~5 days of near-real-time data, so Thermal Twin baselines stay shallow). `FIRMS_MANUAL_REFRESH=false` disables the
public refresh endpoint (the button is hidden in the UI). Attach a Render persistent disk mounted at `/app/backend/data` to keep history across restarts.

## 3. Frontend on Vercel
1. Vercel -> Add New Project -> import this repo -> **Root Directory: `frontend`**.
2. Environment variable: `NEXT_PUBLIC_API_URL` = `https://<service>.onrender.com/api`
3. Deploy, then put the resulting Vercel URL into the Render `CORS_ORIGINS` and redeploy the API.
