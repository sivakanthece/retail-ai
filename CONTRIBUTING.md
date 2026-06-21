# Contributing to Retail AI Inventory System

Thank you for contributing! Please read this guide before opening a PR.

---

## Branch Strategy

```
main        ← production-ready code only. Never push directly.
develop     ← integration branch. All feature branches merge here first.
feature/*   ← new features  (e.g. feature/barcode-scan)
fix/*       ← bug fixes      (e.g. fix/clip-timeout)
docs/*      ← documentation  (e.g. docs/api-reference)
chore/*     ← deps, CI, tooling
```

### Workflow

1. Branch off `develop` (never off `main`)
2. Make your changes, commit with the convention below
3. Open a PR into `develop`
4. CI runs automatically — must pass before review
5. Team lead reviews → squash-merge into `develop`
6. When `develop` is stable, a release PR merges it into `main` → triggers deployment

---

## Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]
[optional footer]
```

| Type       | When to use                                  |
|------------|----------------------------------------------|
| `feat`     | New feature                                  |
| `fix`      | Bug fix                                      |
| `docs`     | Documentation only                           |
| `style`    | Formatting, no logic change                  |
| `refactor` | Code restructuring, no feature/fix           |
| `test`     | Adding or fixing tests                       |
| `chore`    | Build, CI, dependency updates                |

Examples:
```
feat(detection): add barcode fallback after CLIP stage 3
fix(pipeline): handle empty bounding box list gracefully
docs(api): document /nlq/query request format
chore(deps): upgrade ultralytics to 8.3
```

---

## Local Development Setup

```bash
# 1. Clone and enter
git clone https://github.com/YOUR_ORG/retail-ai.git
cd retail-ai

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Fill in your keys
uvicorn main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm start                       # http://localhost:3000
```

---

## Pull Request Checklist

Before opening a PR, confirm:

- [ ] Branched off `develop` (not `main`)
- [ ] Commit messages follow Conventional Commits
- [ ] No API keys or `.env` files committed
- [ ] Backend changes tested locally
- [ ] Frontend builds without errors (`npm run build`)
- [ ] CI passes (lint + build check)
- [ ] PR description explains what changed and why

---

## Environment Variables

Never commit real credentials. Copy `backend/.env.example` → `backend/.env` and fill in your own keys locally. GitHub secrets are managed by the project owner.

---

## Questions?

Open a GitHub Discussion or ping the team on Slack.
