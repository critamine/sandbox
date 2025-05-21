FROM python:3.11.11-slim@sha256:6ed5bff4d7d377e2a27d9285553b8c21cfccc4f00881de1b24c9bc8d90016e82

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