FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# data/ is created at runtime when volume is mounted

EXPOSE 8501

# Run Streamlit - bind to 0.0.0.0 for container access
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
