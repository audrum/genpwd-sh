# Use a minimal, secure Python base image
FROM python:3.13-slim

# Install uv (fast Python installer)
RUN pip install --no-cache-dir uv

# Create a non-root user and group for the app
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Set work directory
WORKDIR /app

# Copy only the files needed for install first (for better layer caching)
COPY pyproject.toml /app/
COPY eff_large_wordlist.txt /app/

# Install dependencies with uv (system install for Docker best practice)
RUN uv pip install --system .

# Now copy the rest of the app (code, templates, static, images)
COPY main.py /app/
COPY templates/ /app/templates/
COPY images/ /app/images/

# Set permissions for the app directory
RUN chown -R appuser:appgroup /app

# Expose Flask port
EXPOSE 9876

# Set environment variables for Flask
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0

# Switch to non-root user
USER appuser

# Healthcheck for the container
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:9876/ || exit 1

# Run the app
CMD ["python", "main.py"] 