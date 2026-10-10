FROM registry.redhat.io/ubi9/python-312-minimal:latest

# Create non-root user
RUN useradd -m -u 1001 appuser

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --frozen --no-dev

# Copy application source
COPY --chown=appuser:appuser config.yaml app.sh ./
COPY --chown=appuser:appuser src/ ./src/

# Switch to non-root user
USER 1001

EXPOSE 8000

# app.sh reads host, port and workers from config.yaml (overridable via env, e.g. APP__HOST=0.0.0.0)
CMD ["./app.sh"]
