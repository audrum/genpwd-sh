# Use a minimal, secure Python base image
FROM python:3.13-slim

# Install uv (fast Python installer)
RUN pip install --no-cache-dir uv

# Create a non-root user and group for the app
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Set work directory
WORKDIR /app

# Copy only the files needed for install first (for better layer caching)
COPY pyproject.toml README.md /app/
COPY eff_large_wordlist.txt /app/

# Install dependencies with uv (system install for Docker best practice)
RUN uv pip install --system .

# Now copy the rest of the app (code, templates, static, images)
COPY main.py /app/
COPY templates/ /app/templates/
COPY images/ /app/images/

# Set permissions for the app directory
RUN chown -R appuser:appgroup /app

# Expose the service port
EXPOSE 9876

# Switch to non-root user
USER appuser

# Healthcheck for the container (no curl in the slim image, so use Python)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:9876/health', timeout=3).status == 200 else 1)"]

# Serve with gunicorn (never the Flask dev server in production)
CMD ["gunicorn", "--bind", "0.0.0.0:9876", "--workers", "2", "--access-logfile", "-", "main:app"]
