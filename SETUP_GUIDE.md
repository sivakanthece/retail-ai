# Setup & Run Guide — Retail AI Inventory System

---

## Step 1 — Install Required Software

Install each tool below. All are free.

### 1.1 Python 3.11
- Download: https://www.python.org/downloads/
- During install: **check "Add Python to PATH"**
- Verify: open Command Prompt and run `python --version`

### 1.2 Node.js 20 (LTS)
- Download: https://nodejs.org/en/download
- Install the **LTS** version
- Verify: `node --version` and `npm --version`

### 1.3 PostgreSQL 15
- Download: https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
- Choose version 15, Windows x86-64
- During install, set a password for the `postgres` superuser (remember it)
- Default port: 5432 — keep it as-is
- Verify: search "pgAdmin 4" in Start Menu — it should open

### 1.4 Redis (Windows)
- Download: https://github.com/microsoftarchive/redis/releases/download/win-3.2.100/Redis-x64-3.2.100.msi
- Install the MSI — it runs as a Windows Service automatically
- Verify: open Command Prompt and run `redis-cli ping` — should reply `PONG`

### 1.5 Visual Studio Code
- Download: https://code.visualstudio.com/
- Install these VS Code extensions after opening:
  - Python (Microsoft)
  - Pylance (Microsoft)
  - ES7+ React/Redux/React-Native snippets

### 1.6 Git (optional but recommended)
- Download: https://git-scm.com/download/win

---

## Step 2 — Get an OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click **"Create new secret key"**
4. Copy the key — it looks like `sk-proj-xxxxxxxxxxxx`
5. Keep it safe — you'll add it to the `.env` file shortly

---

## Step 3 — Set Up the Database

1. Open **pgAdmin 4** (installed with PostgreSQL — find it in Start Menu)
2. Connect using the password you set during install
3. Right-click **"Login/Group Roles"** → **Create** → **Login/Group Role**
   - Name: `retailuser`
   - Password tab: `retailpass`
   - Privileges tab: turn on "Can login"
4. Right-click **"Databases"** → **Create** → **Database**
   - Name: `retaildb`
   - Owner: `retailuser`
5. Click Save

**Alternative (Command Prompt):**
```
psql -U postgres
```
Then paste:
```sql
CREATE USER retailuser WITH PASSWORD 'retailpass';
CREATE DATABASE retaildb OWNER retailuser;
\q
```

---

## Step 4 — Open the Project in VS Code

1. Open VS Code
2. **File → Open Folder**
3. Navigate to and select: `C:\Users\Sivakanth\OneDrive\Desktop\new_projects\retail-ai`
4. Click **"Select Folder"**

---

## Step 5 — Configure Backend Environment

1. In VS Code, open the **Explorer** panel (left sidebar)
2. Navigate into `backend/`
3. Find `.env.example` — right-click → **Copy**, then **Paste** in the same folder
4. Rename the copy to `.env` (remove `.example`)
5. Open `.env` and fill in your OpenAI key:

```
DATABASE_URL=postgresql://retailuser:retailpass@localhost:5432/retaildb
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-proj-your-actual-key-here
OPENAI_MODEL=gpt-4o
SECRET_KEY=any-long-random-string-you-choose
YOLO_MODEL=yolov8n.pt
MAX_UPLOAD_SIZE_MB=20
```

---

## Step 6 — Run the Backend

Open a **Terminal** in VS Code: **Terminal → New Terminal**

```bash
cd backend
```

Create a virtual environment:
```bash
python -m venv venv
```

Activate it:
```bash
venv\Scripts\Activate.ps1
```

> If you get an error about script execution, run this first, then retry:
> ```
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

Install Python packages:
```bash
pip install -r requirements.txt
```

> This takes 3–5 minutes. YOLOv8, PyTorch, and OpenAI SDK are large packages.

Start the backend server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**You should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Test it: open http://localhost:8000/docs in your browser — the API docs should appear.

---

## Step 7 — Run the Frontend

Open a **second terminal** in VS Code: click the **"+"** icon in the terminal panel.

```bash
cd frontend
npm install
```

> This takes 2–3 minutes on first run.

```bash
npm start
```

**You should see:**
```
Compiled successfully!
Local: http://localhost:3000
```

Your browser will open http://localhost:3000 automatically.

---

## Step 8 — Log In and Test

| Username | Password | Role |
|----------|----------|------|
| admin    | admin123 | Full access (edit inventory, view all) |
| manager  | manager123 | Edit inventory |
| analyst  | analyst123 | Read-only + AI queries |

### Quick feature test:
- **Dashboard** — shows inventory stats and charts
- **Detection** — upload any product/shelf photo → YOLOv8 runs detection
- **Inventory** — view/edit all products and stock levels
- **AI Query** — type "Which products are low on stock?" → GPT-4o answers
- **Alerts** — shows auto-generated low-stock alerts

---

## Summary — What Needs to Be Running

Every time you work on this project, make sure these are active:

| Service | How to check | How to start |
|---------|--------------|--------------|
| PostgreSQL | pgAdmin connects | Windows Services → Start "postgresql-x64-15" |
| Redis | `redis-cli ping` returns PONG | Windows Services → Start "Redis" |
| Backend | http://localhost:8000 loads | `uvicorn main:app --reload` (in backend terminal) |
| Frontend | http://localhost:3000 loads | `npm start` (in frontend terminal) |

---

## Troubleshooting

**`venv\Scripts\Activate.ps1` fails**
→ Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` then retry.

**`pip install` errors on psycopg2**
→ Make sure PostgreSQL is installed (provides the required C libraries).

**Backend starts but "could not connect to server"**
→ PostgreSQL is not running. Open Windows Services (search "Services" in Start) → find `postgresql-x64-15` → Start.

**`redis.exceptions.ConnectionError`**
→ Redis is not running. Open Services → find `Redis` → Start.

**YOLOv8 first run is slow**
→ It downloads `yolov8n.pt` (~6MB) on first use — normal. Subsequent runs are instant.

**AI Query returns 401**
→ Your `OPENAI_API_KEY` in `.env` is wrong or missing. Double-check it.

**AI Query returns 503 "Could not connect to OpenAI"**
→ Check your internet connection or firewall settings.

**`npm start` fails with "react-scripts not found"**
→ Run `npm install` again from the `frontend/` folder.

**Port 3000 already in use**
→ Another process is on port 3000. Close it or change the port with `set PORT=3001 && npm start`.

---

## File Structure Reference

```
retail-ai/
├── backend/
│   ├── .env                  ← YOUR CONFIG (create from .env.example)
│   ├── main.py               ← FastAPI app entry point
│   ├── config.py             ← Reads .env settings
│   ├── database.py           ← DB models + auto seed data
│   ├── security.py           ← JWT auth, RBAC, input sanitization
│   ├── requirements.txt      ← Python packages
│   └── routers/
│       ├── auth.py           ← Login / token
│       ├── detection.py      ← YOLOv8 image inference
│       ├── inventory.py      ← Stock CRUD + alerts
│       ├── nlq.py            ← GPT-4o natural language queries
│       └── analytics.py      ← Dashboard metrics
└── frontend/
    ├── package.json
    └── src/
        ├── App.jsx            ← Root layout + routing
        ├── services/api.js    ← Axios API client
        └── pages/
            ├── Login.jsx
            ├── Dashboard.jsx
            ├── Detection.jsx
            ├── InventoryPage.jsx
            ├── NLQPage.jsx
            └── AlertsPage.jsx
```
