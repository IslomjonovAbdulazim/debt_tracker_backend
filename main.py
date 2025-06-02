from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from database import create_tables
from routers import auth, contacts, debts

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title=os.getenv("APP_NAME", "Simple Debt Tracker"),
    description="A simple debt tracking API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    create_tables()

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
app.include_router(debts.router, prefix="/debts", tags=["Debts"])

# Root endpoint
@app.get("/")
def read_root():
    return {
        "message": "Simple Debt Tracker API is running!",
        "docs": "/docs",
        "status": "healthy"
    }

# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "API is working"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)