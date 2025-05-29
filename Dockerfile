# Use the official Python image with Debian
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget unzip gnupg curl \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/chromium

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app files
COPY . /app
WORKDIR /app

# Expose the port Streamlit listens on
EXPOSE 8501

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
