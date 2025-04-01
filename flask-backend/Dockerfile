# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application code to the container
COPY . .

# Expose port 8080 (Cloud Run uses this port)
EXPOSE 8080

# Define environment variable for Flask
ENV FLASK_APP=app.py

# Command to run the application
CMD ["python", "app.py"]
