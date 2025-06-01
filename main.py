# main.py
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import get_db, create_tables

# Create all database tables when app starts
create_tables()

# Create FastAPI app
app = FastAPI(
    title="Debt Tracker API",
    description="API for managing personal debts and contacts",
    version="1.0.0"
)

# Simple test endpoint
@app.get("/")
def read_root():
    return {"message": "Debt Tracker API is running!"}

# Test database connection
@app.get("/test-db")
def test_database(db: Session = Depends(get_db)):
    return {"status": "success", "message": "Database connected successfully!"}