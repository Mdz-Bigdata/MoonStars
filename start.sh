#!/bin/bash

echo "Starting MoonStars..."

# Trap SIGINT and SIGTERM to kill background processes
trap "echo 'Stopping MoonStars...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Start Backend
echo "=== Starting Backend ==="
cd backend
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
echo "Installing backend dependencies..."
./venv/bin/pip install -r requirements.txt

if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

echo "Starting backend server on port 8000..."
./venv/bin/uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start Frontend
echo "=== Starting Frontend ==="
cd frontend
echo "Installing frontend dependencies..."
npm install
echo "Starting frontend server..."
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "========================================="
echo "MoonStars is running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both servers."
echo "========================================="

wait
