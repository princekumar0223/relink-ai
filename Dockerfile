FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose server port
EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000

# Start Relink AI web application
CMD ["python", "run.py"]
