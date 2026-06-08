from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Paste this block right after initializing your 'app'
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://agentapifrontend.pages.dev"],  # Allows your Cloudflare frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # Allows all headers
)

@app.get("/api/apis")
def get_apis():
    return {"message": "Success!"}
