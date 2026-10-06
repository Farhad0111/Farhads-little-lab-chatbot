from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from app.api.routes import router

app = FastAPI(
    title="AI Voice Assistant API",
    description="API for AI voice assistant with speech-to-text, text-to-speech, and chat capabilities",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up templates
# cache_size=0 disables the LRUCache to work around a Python 3.14 / Jinja2 3.1.x
# incompatibility: "TypeError: cannot use 'tuple' as a dict key (unhashable type: 'dict')"
jinja_env = Environment(
    loader=FileSystemLoader("app/templates"),
    cache_size=0,
    auto_reload=True,
)
templates = Jinja2Templates(env=jinja_env)

# Include API routes
app.include_router(router, prefix="/api/v1")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the index.html template"""
    return templates.TemplateResponse(request=request, name="index.html")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8061)