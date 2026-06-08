# AgentAPIs Marketplace — Deployment Guide

## ⚠️ Important Note on Cloudflare

**Cloudflare Pages** only supports **static files** (HTML/CSS/JS). This project has a Python/FastAPI backend with SQLite — it **cannot** run on Cloudflare Pages alone.

You have two options:

---

## Option A: Deploy to Railway (Recommended — Free Tier Available)

Railway supports Python apps with persistent storage. This is the easiest one-click deploy.

### Steps:
1. Create a free account at https://railway.app
2. Click **"New Project" → "Deploy from GitHub"** and push this folder to a GitHub repo, OR use **"Deploy from local"**
3. Railway auto-detects Python via `Procfile`
4. Go to **Variables** tab and add:
   ```
   EASYPAISA_STORE_ID=12345
   EASYPAISA_HASH_KEY=PK_EASYPAISA_SECURE_HASH_KEY_98765
   EASYPAISA_SANDBOX_MODE=True
   BASE_URL=https://your-app-name.up.railway.app
   ```
5. Railway assigns a public URL like `https://agentapis.up.railway.app`
6. Update `BASE_URL` in variables to match this URL
7. Your site is live! 🎉

---

## Option B: Deploy to Render (Free Tier Available)

1. Push this folder to a GitHub repository
2. Go to https://render.com → **New → Web Service**
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment:** Python 3
5. Add the same environment variables as above in the **Environment** tab
6. Deploy!

---

## Option C: Docker (VPS / Any Cloud)

```bash
# Build image
docker build -t agentapis .

# Run container
docker run -d \
  -p 8000:8000 \
  -e EASYPAISA_STORE_ID=12345 \
  -e EASYPAISA_HASH_KEY=your_key_here \
  -e EASYPAISA_SANDBOX_MODE=True \
  -e BASE_URL=https://yourdomain.com \
  -v $(pwd)/marketplace.db:/app/marketplace.db \
  agentapis
```

---

## Option D: Cloudflare (Hybrid Setup)

If you specifically want Cloudflare:

1. **Deploy the backend** to Railway or Render (Options A/B above)
2. **Deploy the frontend** (`static/` folder) to **Cloudflare Pages**:
   - In `static/app.js`, set `API_BASE` to your Railway/Render backend URL
   - Push the `static/` folder to a GitHub repo
   - Connect to Cloudflare Pages → Deploy
3. Add a `_redirects` file in `static/`:
   ```
   /api/*  https://your-backend.railway.app/api/:splat  200
   /callback  https://your-backend.railway.app/callback  200
   ```

---

## Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy env file
cp .env.example .env
# Edit .env as needed

# 3. Run server
uvicorn main:app --reload --port 8000

# 4. Open browser
# http://127.0.0.1:8000
```

---

## Default Admin Login
- **Email:** admin@apimarket.com
- **Password:** admin123

## Testing the Payment Flow (Sandbox)
1. Register a new account (gets 50 PKR free credit)
2. Click "Top Up (Easypaisa)" in the Developer Portal
3. Enter an amount and click "Proceed to Payment"
4. On the mock Easypaisa page, enter PIN: **1234**
5. Payment processes and balance updates ✅

## Architecture Overview
```
Browser (SPA)
    │
    ├── GET /api/apis          → Browse API catalog
    ├── POST /api/login        → Authentication
    ├── POST /api/payment/checkout → Initiate Easypaisa payment
    ├── POST /callback         → Easypaisa webhook (auto-called by mock)
    └── GET /api/proxy/{name}  → AI Agent API proxy (deducts credits)
                                  Header: X-Agent-API-Key: your_key
```
