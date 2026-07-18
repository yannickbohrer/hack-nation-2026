# Hackathon Day — What's Ready & How to Launch

## What Was Done Tonight

### 1. Reviewed & improved your original bootstrap plan
- Identified 10 issues (biggest: no AI integration for an AI hackathon)
- Wrote an improved plan → [PREPARATION_PLANNING.md](file:///home/yannick/Code/hack-nation/PREPARATION_PLANNING.md)

### 2. Scaffolded the full project

| Layer | Files | What it does |
|-------|-------|-------------|
| **Backend** | [main.py](file:///home/yannick/Code/hack-nation/backend/main.py), [ai_client.py](file:///home/yannick/Code/hack-nation/backend/services/ai_client.py), [requirements.txt](file:///home/yannick/Code/hack-nation/backend/requirements.txt), [Dockerfile](file:///home/yannick/Code/hack-nation/backend/Dockerfile) | FastAPI server with a `/api/status` health check and a `/api/chat` endpoint that streams OpenAI responses via SSE |
| **Frontend** | [App.jsx](file:///home/yannick/Code/hack-nation/frontend/src/App.jsx), [Chat.jsx](file:///home/yannick/Code/hack-nation/frontend/src/components/Chat.jsx), [useStream.js](file:///home/yannick/Code/hack-nation/frontend/src/hooks/useStream.js), [index.css](file:///home/yannick/Code/hack-nation/frontend/src/index.css) | React + Vite app with a dark-mode chat UI that consumes the SSE stream in real time |
| **Infra** | [docker-compose.yml](file:///home/yannick/Code/hack-nation/docker-compose.yml), [Makefile](file:///home/yannick/Code/hack-nation/Makefile) | One-command launch with healthcheck, `depends_on`, and `env_file` |
| **DX** | [.gitignore](file:///home/yannick/Code/hack-nation/.gitignore), [.env.example](file:///home/yannick/Code/hack-nation/.env.example), [.env](file:///home/yannick/Code/hack-nation/.env), [README.md](file:///home/yannick/Code/hack-nation/README.md) | Secrets management, Devpost-ready README template |

### 3. Installed all dependencies
- **Frontend**: `npm install` done — `node_modules/` ready in `frontend/`
- **Backend**: Python venv created at `backend/venv/` with all 28 packages installed (FastAPI, OpenAI SDK, sse-starlette, etc.)

---

## Tomorrow: Step by Step

### Before the hackathon starts (do this first thing)

```bash
# 1. Open the project
cd ~/Code/hack-nation

# 2. Add your OpenAI API key
nano .env
# Change: OPENAI_API_KEY=sk-your-key-here
# To:     OPENAI_API_KEY=sk-actual-key

# 3. Start the full stack
make up
# (or: docker compose up --build)
```

First build will take ~1-2 minutes (Docker pulls base images + installs deps).  
After that, verify:
- http://localhost:5173 → you should see the chat UI with a green "API is operational" badge
- Type a message → you should see streaming AI responses

> If `make up` fails because Docker isn't running, start Docker Desktop first.

### When the challenge is revealed (noon ET)

**Minutes 0–5**: Read the challenge. Pick your angle.

**Minutes 5–15**: Adapt the boilerplate:
- Open [ai_client.py](file:///home/yannick/Code/hack-nation/backend/services/ai_client.py) — update the `system_prompt` parameter in your `/api/chat` call to match the challenge
- Open [main.py](file:///home/yannick/Code/hack-nation/backend/main.py) — add any new endpoints you need
- Open [App.jsx](file:///home/yannick/Code/hack-nation/frontend/src/App.jsx) — rename the header, adjust the layout

**Minutes 15–30**: You should have a working AI-powered demo tailored to the challenge. Everything after this is iteration.

### Key files you'll edit most

| Want to... | Edit this |
|-----------|-----------|
| Change the AI's behavior / system prompt | [ai_client.py](file:///home/yannick/Code/hack-nation/backend/services/ai_client.py) |
| Add new API endpoints | [main.py](file:///home/yannick/Code/hack-nation/backend/main.py) |
| Change the UI layout | [App.jsx](file:///home/yannick/Code/hack-nation/frontend/src/App.jsx) |
| Modify the chat component | [Chat.jsx](file:///home/yannick/Code/hack-nation/frontend/src/components/Chat.jsx) |
| Change colors / styling | [index.css](file:///home/yannick/Code/hack-nation/frontend/src/index.css) |

### Useful commands

```bash
make up                # Start everything
make down              # Stop everything
make logs              # Tail all logs
make backend-shell     # Shell into backend container
make rebuild-backend   # Rebuild only backend
```

### Before submitting (last hour)

1. Fill in [README.md](file:///home/yannick/Code/hack-nation/README.md) — it's pre-templated for Devpost
2. Record a demo video
3. Push to GitHub
4. Submit on Devpost
