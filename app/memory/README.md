# `app/memory/`

Short-term session memory and long-term keyword memory.

## Files

| File | Purpose |
|------|---------|
| `session.py` | `SessionManager` — conversation history per session |
| `long_term.py` | `LongTermMemory` — tagged keyword recall |
| `system.py` | `MemorySystem` facade + session summarization |

## Examples

```python
from app.memory.session import session_manager
from app.memory.system import memory_system

session = session_manager.create()
session_manager.add_message(session.session_id, "user", "I prefer Python")

memory_system.remember("User prefers Python", tags=["preference"])
print(memory_system.recall("python"))
print(memory_system.summarize_session(session.session_id))
```
