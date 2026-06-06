FROM python:3.12-slim

# Install only the packages needed at runtime.
# curl: used by the health-check in docker-compose.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user — minimises blast radius if the container is
# compromised.  UID/GID 1001 avoids conflicts with common host users.
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install Python dependencies before copying the full source so that Docker
# can cache this layer and only re-run it when pyproject.toml changes.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

# Copy application source, Alembic files, and entrypoint.
COPY app/        ./app/
COPY alembic/    ./alembic/
COPY alembic.ini ./alembic.ini
COPY docker/entrypoint.sh ./entrypoint.sh

RUN chmod +x /app/entrypoint.sh \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
