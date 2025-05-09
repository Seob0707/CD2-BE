FROM python:3.12.8-bookworm

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
WORKDIR /src

# Install system dependencies required by Faiss
RUN apt-get update && \
    apt-get install -y libopenblas-dev libomp-dev wget && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==1.8.4"

# Copy dependency definitions
COPY pyproject.toml poetry.lock ./

# Configure Poetry to install into the system Python environment and install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Download RDS CA certificate bundle
RUN mkdir -p /src/certs && \
    wget https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
         -O /src/certs/rds-ca-2019-root.pem

# Copy application code and migrations
COPY api ./api
COPY migrations ./migrations

# Set timezone
ENV TZ=Asia/Seoul

# Start the application with Uvicorn
ENTRYPOINT ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--reload", "--log-level", "debug"]