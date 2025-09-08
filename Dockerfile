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
COPY src .

# Make port 9429 available to the world outside this container
EXPOSE 9429

# Run main.py when the container launches
CMD ["python", "web.py"]