# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a wheels directory
ENV PATH=/root/.local/bin:$PATH
ENV PIP_ROOT_USER_ACTION=ignore
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

# Memory optimization for 512MB environments (Render Free Tier)
ENV MALLOC_ARENA_MAX=2
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV VECLIB_MAXIMUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1

# Copy project files
COPY app/ ./app/
COPY main.py .
COPY README.md .

# Copy pre-built catalog to prevent memory spike on startup
COPY catalog/ ./catalog/

EXPOSE 8000

# Start FastAPI application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
