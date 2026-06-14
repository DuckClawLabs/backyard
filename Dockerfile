FROM python:3.11-slim

WORKDIR /app

# Install system deps (git needed for file ops)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system -e ".[server]"

# Copy source
COPY src/ ./src/
COPY src/backyard/dashboard/ ./src/backyard/dashboard/

EXPOSE 8000

CMD ["uvicorn", "backyard.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
