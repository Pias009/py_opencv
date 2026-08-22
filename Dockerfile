FROM python:3.10-slim

# Install system dependencies for OpenCV, FFmpeg, and ReportLab
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and models
COPY . .

# Expose port (default 5000, dynamic on Render/Railway)
EXPOSE 5000

ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Run server with python directly to support streaming & multithreading
CMD ["python", "app/server.py"]
