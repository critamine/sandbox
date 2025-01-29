FROM python:3.13.1-slim@sha256:026dd417a88d0be8ed5542a05cff5979d17625151be8a1e25a994f85c87962a5

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

# Switch to non-root user to run app
USER appuser

CMD ["/bin/sh", "-c", "uvicorn src.main:app --host ${HOST} --port ${PORT}"]
