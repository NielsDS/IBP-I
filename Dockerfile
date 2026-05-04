# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools and copy project files.
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

# Install the package with the API extra into a prefix so we can copy it cleanly.
RUN pip install --no-cache-dir --prefix=/install ".[api]"

# ── Runtime stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Create a non-root user.
RUN useradd --system --uid 1001 --create-home appuser

WORKDIR /app

# Copy only the installed Python artifacts from the builder.
COPY --from=builder /install /usr/local

# No extra files needed at runtime beyond the installed package.

USER appuser

EXPOSE 8000

ENV SS_HOST=0.0.0.0 \
    SS_PORT=8000 \
    SS_WORKERS=1 \
    SS_LOG_LEVEL=INFO \
    SS_LOG_JSON=true \
    SS_DOCS_ENABLED=true

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["safety-stock-api"]
