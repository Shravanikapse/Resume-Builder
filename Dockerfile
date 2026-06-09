# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install wkhtmltopdf and its dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 10000

# Run the application using Gunicorn
CMD gunicorn app:app -w 4 -b 0.0.0.0:${PORT:-10000}
