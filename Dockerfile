# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a wheels directory
ENV PATH=/root/.local/bin:$PATH
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final image
FROM python:3.11-slim as runner

WORKDIR /app

# Install runtime dependencies if needed (e.g. libgomp for FAISS on Linux slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app /app

# Set PATH to find installed user packages
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Copy project files
COPY app/ ./app/
COPY main.py .
COPY README.md .

# Create directory for catalog and pre-initialize database
RUN mkdir -p catalog

# Build catalog and FAISS index during container building or start
# (Note: Building at startup is safer to read current env vars if required,
# but we can pre-create folders)

EXPOSE 8000

# Start FastAPI application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
