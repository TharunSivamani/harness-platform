# ForgeAI Console

Next.js UI for the ForgeAI agent operating system.

## Pages

- `/` — Chat (creates session, calls `POST /chat`)
- `/tools` — Tool inspector + direct `POST /tool`
- `/sessions` — List/create sessions and inspect history
- `/artifacts` — Upload + download artifacts
- `/ops` — Metrics, event bus, execution recorder

## Run with backend

```bash
# terminal 1
uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

API base URL is set by `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`).

## Files

| Path | Purpose |
|------|---------|
| `src/lib/api.ts` | Typed fetch client for ForgeAI REST API |
| `src/components/AppShell.tsx` | Brand shell + navigation |
| `src/app/page.tsx` | Chat console |
| `src/app/tools/page.tsx` | Tools discovery/execution |
| `src/app/sessions/page.tsx` | Session explorer |
