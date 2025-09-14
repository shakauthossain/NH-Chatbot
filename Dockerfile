# Use an official lightweight Python image
FROM python:3.10-slim

# Set environment variables to prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create Hugging Face cache directory and set permissions
RUN mkdir -p /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /home/appuser/.cache

# Set Hugging Face cache environment variable
ENV HF_HOME=/home/appuser/.cache/huggingface

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the entire application
COPY . .

# Restrict file permissions for production (read/write for owner, read for group)
RUN chmod 640 /app/faqs.csv

# Change ownership to non-root user
RUN chown -R appuser:appuser /app


# Expose the port FastAPI will run on (using 8002)
EXPOSE 8002

# Switch to non-root user
USER appuser

# Run the FastAPI app using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

