FROM python:3.10-slim

# Install dependencies
RUN apt-get update && \
    apt-get install -y build-essential cmake libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev && \
    pip install --upgrade pip setuptools wheel

# Install dlib and other dependencies
RUN pip install dlib==19.22.0

# Copy your code
WORKDIR /app
COPY . /app

# Install project dependencies
RUN pip install -r requirements.txt

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
