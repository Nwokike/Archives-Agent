# Use the official, lightweight Python 3.13 image
FROM python:3.13-slim

# Force Python to not buffer outputs (makes Google Cloud logs work instantly)
ENV PYTHONUNBUFFERED True

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first (this speeds up future builds)
COPY requirements.txt ./

# Install all the dependencies without saving massive cache files
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the rest of your agent files into the container
COPY . ./

# Start the FastAPI server on port 8080, open to the internet (0.0.0.0)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
