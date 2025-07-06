FROM python:3.10-slim

# Install system dependencies for dlib
RUN apt-get update && apt-get install -y \
    build-essential cmake libopenblas-dev liblapack-dev \
    libx11-dev libgtk-3-dev libboost-python-dev \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy and install
COPY . /app
RUN pip install --upgrade pip
RUN pip install wheel
RUN pip install -r requirements.txt

# Start your app
CMD ["gunicorn", "your_module:app"]
