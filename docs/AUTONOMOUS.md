# Chat loop (product autonomy)

ForgeAI autonomy is **inside chat**, not a separate `/agent/autonomous` product flow.

```text
user message
  -> persist prompt
  -> LLM with tool schemas
  -> while tool_calls: execute -> persist tool result -> LLM again
  -> persist final assistant message
```

APIs:

- `POST /sessions/{id}/chat`
- `GET /sessions/{id}/stream`

CLI:

```bash
forge chat "list files and summarize"
```

Legacy autonomous runner may still exist for experiments, but the UI/CLI use the chat loop.
