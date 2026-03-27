# Stage 1: Build stage
# ghcr.io/astral-sh/uv offers a specialized image with uv pre-installed.
# We use the alpine variant for a smaller build environment.
FROM ghcr.io/astral-sh/uv:0.9.27-python3.13-alpine AS builder

# Set the working directory
WORKDIR /app

# Enable bytecode compilation for performance (Cloud Run benefit)
ENV UV_COMPILE_BYTECODE=1

# Copy only the files needed for dependency resolution
# This maximizes Docker's layer caching.
COPY pyproject.toml uv.lock ./

# Install dependencies into a separate site-packages directory
# We use --frozen for absolute repeatability from the uv.lock file
# And --no-dev to exclude developer tools.
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime stage
# We use python:3.13-slim for a tiny but highly compatible final image.
FROM python:3.13-slim

# Force Python output to be sent to terminal without buffer (important for GCP logging)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set final working directory
WORKDIR /app

# Copy the application dependencies from the builder stage
# /app/.venv contains the entire environment.
COPY --from=builder /app/.venv /app/.venv

# Add the virtualenv's binary path to the PATH so we can run uvicorn
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application source code
COPY . .

# Metadata and Copyright (Kiri Research Labs)
LABEL maintainer="Onyeka Nwokike <nwokikeonyeka@gmail.com>"
LABEL org.opencontainers.image.description="Nwokike/Archives-Agent - Professional Archiving Engine"

# Expose port (Cloud Run defaults to 8080)
EXPOSE 8080

# Use uvicorn directly from the path.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
