FROM python:3.13.3-slim@sha256:56a11364ffe0fee3bd60af6d6d5209eba8a99c2c16dc4c7c5861dc06261503cc

WORKDIR /app

# Dependencies and system setup combined
COPY requirements.txt .
RUN groupadd -r appgroup && \
    useradd -r -g appgroup appuser && \
    pip install --root-user-action=ignore --no-cache-dir --require-hashes -r requirements.txt

# Application code
COPY src/ ./src/
RUN chown -R appuser:appgroup /app

# Configuration
ENV PYTHONPATH=/app/src
ENV PORT=8000
ENV HOST=0.0.0.0
ENV UV_LOGLVL=debug

# Switch to non-root user to run app
USER appuser

CMD ["/bin/sh", "-c", "uvicorn src.main:app --host ${HOST} --port ${PORT} --log-level ${UV_LOGLVL}"]