#!/bin/bash
# start.sh - Script to set environment variables and run the Flask app

# Set environment variables
export DB_HOST=127.0.0.1
export DB_NAME=posterdb
export DB_USER=postgres
export DB_PASSWORD="Q[gQ)k8t:o6DTl/Z"
export JWT_SECRET_KEY="your-secret-key"
export POSTER_BUCKET_NAME="poster-app-photos-137340833578"
export PORT=8080

# Optionally, print the environment variables for verification
echo "DB_HOST: $DB_HOST"
echo "DB_NAME: $DB_NAME"
echo "DB_USER: $DB_USER"
echo "JWT_SECRET_KEY: $JWT_SECRET_KEY"
echo "POSTER_BUCKET_NAME: $POSTER_BUCKET_NAME"
echo "PORT: $PORT"

# Start the Flask app
python3 app.py
