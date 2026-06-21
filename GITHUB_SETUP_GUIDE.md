# GitHub Setup Guide — Retail AI Inventory System
*Step-by-step from zero to live pipeline*

---

## Overview

```
Your computer (VS Code)
      │
      │  git push
      ▼
GitHub Repository
      │
      ├── Pull Request → CI workflow runs (lint + build)
      │
      └── Merge to main → Deploy workflow runs → Hugging Face Spaces (live)
```

---

## PART 1 — One-Time Setup (You do this once)

### Step 1 — Create the GitHub Repository

1. Go to **https://github.com/new**
2. Fill in:
   - **Repository name:** `retail-ai`
   - **Visibility:** Private (recommended) or Public
   - **DO NOT** tick "Add a README" (we already have one)
3. Click **Create repository**
4. Copy the URL shown — it will look like:
   `https://github.com/YOUR_USERNAME/retail-ai.git`

---

### Step 2 — Open the project in VS Code

1. Open VS Code
2. **File → Open Folder** → select `C:\Users\Sivakanth\OneDrive\Desktop\new_projects\retail-ai`
3. Open the integrated terminal: **Terminal → New Terminal** (or `Ctrl+\``)

---

### Step 3 — Connect local repo to GitHub

In the VS Code terminal, run these commands one by one:

```bash
# Check the current state
git status

# Connect to GitHub (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/retail-ai.git

# Verify the remote is set
git remote -v
```

---

### Step 4 — Stage and commit ONLY safe files

The `.gitignore` already excludes secrets, venv, node_modules, and image libraries.
Run this to double-check what will be committed:

```bash
git status
```

You should NOT see any of these in the list — if you do, stop and tell the team:
- `backend/.env`
- `backend/venv/`
- `frontend/node_modules/`
- `backend/product_library/`

Now stage everything safe:

```bash
git add .
git status   # review the list one more time
```

Make the first commit:

```bash
git commit -m "chore: initial project setup — FastAPI + React + CLIP pipeline"
```

---

### Step 5 — Create the develop branch and push both branches

```bash
# Rename current branch to main (if not already)
git branch -M main

# Push main to GitHub
git push -u origin main

# Create and push the develop branch
git checkout -b develop
git push -u origin develop
```

After this, go to **GitHub → your repo → Settings → Branches**:
- Set `main` as the default branch
- Add a branch protection rule for `main`:
  - ✅ Require a pull request before merging
  - ✅ Require status checks to pass (select `backend-lint-test` and `frontend-lint`)
  - ✅ Do not allow bypassing the above settings

---

### Step 6 — Add GitHub Secrets (for CI and deployment)

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:

| Secret name          | Value                                      |
|----------------------|--------------------------------------------|
| `OPENAI_API_KEY`     | Your OpenAI key                            |
| `GOOGLE_API_KEY`     | Your Google/Gemini key                     |
| `GROQ_API_KEY`       | Your Groq key                              |
| `DOCKERHUB_USERNAME` | Your Docker Hub username                   |
| `DOCKERHUB_TOKEN`    | Docker Hub access token (see note below)   |
| `HF_TOKEN`           | Hugging Face write token                   |
| `HF_SPACE`           | Your HF space e.g. `YourName/retail-ai`   |

**To get a Docker Hub token:**
1. Login at hub.docker.com → Account Settings → Security → New Access Token
2. Copy the token and paste it as `DOCKERHUB_TOKEN`

**To get a Hugging Face token:**
1. huggingface.co → Settings → Access Tokens → New token (Write permission)

---

### Step 7 — Set the deploy target variable

Go to: **GitHub repo → Settings → Secrets and variables → Actions → Variables tab → New repository variable**

| Variable name   | Value  |
|-----------------|--------|
| `DEPLOY_TARGET` | `hf`   |

Set to `hf` for Hugging Face Spaces, or `server` if deploying to a VPS.

---

## PART 2 — Hugging Face Spaces Setup (first time)

1. Go to **https://huggingface.co/spaces**
2. Click **Create new Space**
3. Fill in:
   - **Space name:** `retail-ai`
   - **SDK:** Docker
   - **Visibility:** Public or Private
4. Go to the Space **Settings → Variables and Secrets** and add:
   - `SECRET_KEY` → a long random string
   - `OPENAI_API_KEY` → your key
   - `GOOGLE_API_KEY` → your key
   - `GROQ_API_KEY` → your key
   - `DATABASE_URL` → `sqlite:///./retail.db`
5. The GitHub Actions `deploy.yml` will push code to HF automatically on every merge to `main`

---

## PART 3 — Daily Collaboration Workflow (for you and your colleagues)

### Starting a new feature or fix

```bash
# Always start from develop
git checkout develop
git pull origin develop

# Create a branch named after what you're doing
git checkout -b feature/barcode-scan
# or
git checkout -b fix/clip-timeout
```

### Making changes and committing

```bash
# After making your changes
git add .
git commit -m "feat(detection): add barcode fallback after CLIP stage 3"

# Push your branch
git push origin feature/barcode-scan
```

### Opening a Pull Request

1. Go to **GitHub → your repo**
2. You'll see a yellow banner: **"Compare & pull request"** — click it
3. Set:
   - **base:** `develop` (NOT main)
   - **compare:** your branch
4. Fill in the PR template (what changed, how to test)
5. Click **Create pull request**

CI will run automatically. You'll see green ✅ or red ❌ checks on the PR.

### After CI passes

- A teammate reviews the PR
- They approve and **Squash and merge** into `develop`
- Delete the feature branch when prompted

### Releasing to production

When `develop` is stable and tested:

```bash
git checkout main
git pull origin main
git merge develop
git push origin main
```

This triggers the **deploy workflow** → builds Docker image → pushes to HF Spaces → live in ~3 minutes.

---

## PART 4 — VS Code Extensions (install these)

Open VS Code → Extensions (`Ctrl+Shift+X`) and install:

| Extension                    | Why                                    |
|------------------------------|----------------------------------------|
| **GitHub Pull Requests**     | Manage PRs directly in VS Code         |
| **GitLens**                  | Inline blame, history, branch compare  |
| **Python** (Microsoft)       | IntelliSense + linting                 |
| **Pylance**                  | Python type checking                   |
| **ESLint**                   | JavaScript/React linting               |
| **Prettier**                 | Auto-format on save                    |
| **Docker**                   | Manage containers from VS Code         |
| **REST Client** (optional)   | Test API endpoints from .http files    |

---

## PART 5 — What happens automatically

| Event                        | What CI/CD does                                    |
|------------------------------|----------------------------------------------------|
| You open a PR into `develop` | Runs lint + build check. PR blocked if it fails.   |
| PR merged into `develop`     | Runs lint + build check again on develop.          |
| Merge `develop` into `main`  | Builds Docker image → pushes to Docker Hub → syncs to Hugging Face Spaces → app is live |
| Manual trigger               | You can re-run the deploy from GitHub → Actions → Deploy → Run workflow |

---

## Quick Reference — Common Git Commands

```bash
git status                      # see what changed
git pull origin develop         # get latest changes
git log --oneline -10           # see recent commits
git diff                        # see unstaged changes
git stash                       # save work temporarily
git stash pop                   # restore saved work
git branch                      # list branches
git checkout -b fix/my-fix      # create + switch to new branch
git push origin fix/my-fix      # push branch to GitHub
```

---

## Troubleshooting

**CI fails on "ruff" lint errors**
Run `ruff check backend/ --fix` locally, commit the fixes, push again.

**Frontend build fails in CI**
Run `cd frontend && npm run build` locally to see the error before pushing.

**Deploy workflow fails on HF push**
Check that `HF_TOKEN` secret is set with **write** permission and `HF_SPACE` matches exactly `Username/space-name`.

**".env file is showing in git status"**
Run `git rm --cached backend/.env` then commit. The .gitignore will prevent it going forward.
