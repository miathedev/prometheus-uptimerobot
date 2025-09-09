# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV UPTIMEROBOT_HOST 0.0.0.0

# Set the working directory in the container
WORKDIR /app

# Install any needed packages specified in requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bundle app source inside Docker image

# Copy the app source to the correct location
COPY src/ws/prometheus_uptimerobot /app/src/ws/prometheus_uptimerobot

# Make port 9429 available to the world outside this container
EXPOSE 9429

# Add healthcheck for /health endpoint
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
	CMD curl --fail http://localhost:9429/health || exit 1

# Run the web server when the container launches
CMD ["python", "src/ws/prometheus_uptimerobot/web.py"]