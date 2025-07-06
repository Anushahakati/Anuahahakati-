FROM python:3.10-slim

# Install system packages for dlib
RUN apt-get update && \
    apt-get install -y build-essential cmake libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev && \
    pip install --upgrade pip setuptools wheel

# Pre-install dlib to avoid memory crashes
RUN pip install dlib==19.22.0

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install remaining Python dependencies
RUN pip install -r requirements.txt

# Run the app with gunicorn (adjust `app:app` to match your Python file and Flask app name)
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
