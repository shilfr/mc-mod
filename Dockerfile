FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render uses port 10000 by default
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]

