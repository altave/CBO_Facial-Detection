# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the application code to the container
COPY ./src /app/src
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy environment variables
COPY environment_variables.env /app/.env

# Expose any ports the app runs on (if needed, like Flask's default port 5000)
EXPOSE 5000

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1

# Use the wait-for-rabbit.sh script to start the application
CMD ["python", "src/main.py"]
