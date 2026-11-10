FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/data/refundguard.sqlite3
WORKDIR /app
# The slim image can lag Debian security updates. Upgrade installed packages
# before the vulnerability scan so a published zlib fix does not fail the build.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/lock.txt ./requirements/lock.txt
RUN pip install --no-cache-dir -r requirements/lock.txt && useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser /data
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts/__init__.py scripts/manage.py ./scripts/
COPY deploy/entrypoint.py ./deploy/entrypoint.py
# Railway mounts volumes as root. The entrypoint fixes ownership, then drops
# permanently to UID/GID 10001 before importing or serving the application.
# Attach /data using a Railway persistent volume (Docker VOLUME is unsupported there).
EXPOSE 8000
ENTRYPOINT ["python", "/app/deploy/entrypoint.py"]
