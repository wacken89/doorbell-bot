FROM python:3.11-slim

WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Verify alembic is installed
RUN which alembic || echo "alembic not found in PATH"

COPY . .

# Ensure proper permissions
RUN chmod -R 755 /app

# Add the current directory to PYTHONPATH
ENV PYTHONPATH=/app

# The entrypoint is now handled in docker-compose.yml
CMD ["python", "run_migrations.py"] 