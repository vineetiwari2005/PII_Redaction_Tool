# Deployment Guide — PII Redaction Tool (Scalar)

This guide walks through deploying the project from scratch using your own GitHub, Vercel, and Render accounts.

---

## Step 1: Create GitHub Repository

1. Go to [github.com](https://github.com) and sign in (or create a new account).
2. Click **New Repository** → Name it `PII_Redaction_Tool` (or any name you like).
3. Set it to **Public** and click **Create Repository**.
4. From this project folder, push the code:

```bash
cd d:\OA\Scalar\Assignment\PII_Redaction_Tool_Scalar
git init
git add .
git commit -m "Initial commit — PII Redaction Tool"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/PII_Redaction_Tool.git
git push -u origin main
```

---

## Step 2: Deploy Backend on Render (Free Tier)

1. Go to [render.com](https://render.com) and sign up with your GitHub account.
2. Click **New** → **Web Service** → **Connect Repository** → Select the repo you just pushed.
3. Configure the service:
   - **Name**: `pii-redaction-api` (or any name)
   - **Region**: Pick the closest one
   - **Branch**: `main`
   - **Root Directory**: Leave blank (root of repo)
   - **Runtime**: Python
   - **Build Command**:
     ```
     pip install -r requirements.txt && python -m spacy download en_core_web_sm
     ```
   - **Start Command**:
     ```
     python -m uvicorn api:app --host 0.0.0.0 --port $PORT
     ```
4. Under **Environment Variables**, add:
   - `SPACY_MODEL` = `en_core_web_sm`
   - `PYTHON_VERSION` = `3.11.9`
5. Select **Free** plan → Click **Create Web Service**.
6. Wait 3–5 minutes for the build. Once deployed, note the URL (e.g., `https://pii-redaction-api-xxxx.onrender.com`).
7. Test it: visit `https://YOUR_RENDER_URL/api/health` — you should see `{"status": "ok", "model": "en_core_web_sm"}`.

> **Note**: Free-tier Render instances sleep after 15 minutes of inactivity. The first request after sleep takes ~30 seconds (cold start).

---

## Step 3: Deploy Frontend on Vercel (Free Tier)

1. Go to [vercel.com](https://vercel.com) and sign up with your GitHub account.
2. Click **Add New** → **Project** → **Import** → Select your repo.
3. Configure:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `frontend`
4. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL` = `https://YOUR_RENDER_URL` (the Render URL from Step 2, WITHOUT trailing slash)
5. Click **Deploy**. Vercel will build and deploy automatically (~1 min).
6. Once deployed, open the Vercel URL and test by uploading a `.docx` file.

---

## Step 4: Verify Everything Works

1. Open your Vercel frontend URL in a browser.
2. Open **DevTools** (F12) → Console tab.
3. You should see: `[PII Tool] Backend: https://your-render-url.onrender.com`
4. Upload a `.docx` file → Click "Redact Document".
5. The first request may take 30–60 seconds (cold start). Subsequent requests should be faster.

---

## Local Development

If you want to run everything locally:

```bash
# Terminal 1 — Backend
pip install -r requirements.txt
python -m spacy download en_core_web_lg
python -m uvicorn api:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

The frontend will run at `http://localhost:3000` and automatically connect to `http://localhost:8000`.

---

## File Structure

```
PII_Redaction_Tool_Scalar/
├── settings.py              ← Configuration (thresholds, deny-lists)
├── scanner.py               ← PII detection (Presidio + custom recognizers)
├── docx_processor.py        ← .docx read/write with run-level mapping
├── redactor.py              ← Blackout mapper (█████ replacement)
├── glossary_extractor.py    ← Auto-parses definitions section
├── pipeline.py              ← Main orchestration (CLI + API entry point)
├── api.py                   ← FastAPI web service
├── evaluator.py             ← Accuracy measurement (P/R/F1)
├── requirements.txt         ← Python dependencies
├── render.yaml              ← Render deployment blueprint
├── ground_truth_sample.json ← Hand-labelled test data
├── README.md                ← Project documentation
├── EVALUATION_STRATEGY.md   ← Evaluation methodology
└── frontend/                ← Next.js + Tailwind frontend
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx
    │   └── globals.css
    └── package.json
```
