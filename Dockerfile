FROM python:3.11-slim

WORKDIR /app

# Prefer uv for reproducible installs; fallback to pip if uv.lock absent
COPY pyproject.toml uv.lock* requirements.txt* ./
RUN if [ -f uv.lock ]; then \
      pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-editable; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY app ./app
COPY workspace ./workspace

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
