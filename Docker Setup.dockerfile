# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Start the FastAPI application
CMD ["uvicorn", "Real Time Nlp:app", "--host", "0.0.0.0", "--port", "8000"]
