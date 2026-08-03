# ForgeAI Console

ChatGPT-style session UI.

## Run

```bash
# API
uvicorn app.main:app --reload --port 8000

# UI
npm install
npm run dev
```

Open http://localhost:3000

## Features

- Left sidebar sessions + new chat
- Main transcript (user/assistant/tool)
- Uploads into session
- Right rail session files
- Token stats per session / user
- Soft user switch via `X-Forge-User` (`local` by default)
