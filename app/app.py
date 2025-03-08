# app.py
import os
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import imgkit
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, HttpUrl, AnyHttpUrl

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

# Configuration
API_TOKEN = os.getenv("API_TOKEN", "DaduBhogLagaRaheHai")  # Change this in production
MAX_DOWNLOADS = int(os.getenv("MAX_DOWNLOADS", "5"))  # Default max downloads per image
ROOT_PATH = str(os.getenv("ROOT_PATH", "/html_to_image"))  # Default max downloads per image
#ROOT_PATH = "/html_to_image"
HOST_IMAGES = int(os.getenv("HOST_IMAGES", "1"))  # Default max downloads per image
IMAGE_EXPIRY_DAYS = int(os.getenv("IMAGE_EXPIRY_DAYS", "3"))  # Default expiry in days
STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")  # Base URL for absolute links

# Create security scheme
security = HTTPBearer()

# Create the FastAPI app
app = FastAPI(
    title="HTML to Image API",
    description="API for converting HTML to images",
    version="1.0.0",
    root_path=ROOT_PATH,
)


# Models
class HTMLRequest(BaseModel):
    html: str


class URLRequest(BaseModel):
    url: HttpUrl = "https://automationtester.in"


class ImageResponse(BaseModel):
    image_url: AnyHttpUrl
    image_id: str
    downloads_remaining: int
    expires_at: datetime


# Image metadata store
image_metadata: Dict[str, Dict] = {}


# Token verification function
def verify_token_from_credentials(credentials: HTTPAuthorizationCredentials):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token"
        )
    return True


# Scheduled cleanup function (could be replaced with a background task)
def cleanup_old_images():
    current_time = datetime.now()
    images_to_remove = []

    for image_id, metadata in image_metadata.items():
        # Check if image has expired
        if current_time > metadata["expires_at"]:
            images_to_remove.append(image_id)
        # Check if downloads are used up
        elif metadata["downloads_remaining"] <= 0:
            images_to_remove.append(image_id)

    # Remove expired images
    for image_id in images_to_remove:
        image_path = STATIC_DIR / f"{image_id}.png"
        if image_path.exists():
            os.remove(image_path)
        image_metadata.pop(image_id, None)


# Utility function to convert HTML to image
def convert_html_to_image(html_content: str, image_path: str):
    options = {
        "format": "png",
        "quiet": "",
        "quality": 85,
    }

    try:
        imgkit.from_string(html_content, image_path, options=options)
        return True
    except Exception as e:
        print(f"Error converting HTML to image: {e}")
        return False


# Helper to generate absolute URL
def get_absolute_url(path: str) -> str:
    # Ensure path starts with '/' and BASE_URL doesn't end with '/'
    if not path.startswith("/"):
        path = "/" + path
    base_url = BASE_URL.rstrip("/")
    root_path = ROOT_PATH.rstrip("/")
    return f"{base_url}{root_path}{path}"

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        #openapi_url=f"/html_to_image/openapi.json",  # Corrected path
        openapi_url=f"{ROOT_PATH}/openapi.json",  # Corrected path
        title="HTML to Image API Docs"
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return get_openapi(
        title="HTML to Image",
        version="1.0.0",
        description="API documentation",
        routes=app.routes,
    )

# API Endpoints
@app.post("/convert/html", response_model=ImageResponse)
async def convert_html_to_image_endpoint(
    request: HTMLRequest, credentials: HTTPAuthorizationCredentials = Depends(security)
):
    verify_token_from_credentials(credentials)
    cleanup_old_images()  # Clean up on each request

    image_id = str(uuid.uuid4())
    image_path = str(STATIC_DIR / f"{image_id}.png")

    if not convert_html_to_image(request.html, image_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert HTML to image",
        )

    # Set expiry date
    expires_at = datetime.now() + timedelta(days=IMAGE_EXPIRY_DAYS)
    # max_downloads = (
    #     request.max_downloads if request.max_downloads is not None else MAX_DOWNLOADS
    # )
    max_downloads = MAX_DOWNLOADS

    # Store metadata
    image_metadata[image_id] = {
        "downloads_remaining": max_downloads,
        "expires_at": expires_at,
        "created_at": datetime.now(),
    }

    # Generate absolute URL for response
    image_url = get_absolute_url(f"/download/{image_id}")

    return ImageResponse(
        image_url=image_url,
        image_id=image_id,
        downloads_remaining=max_downloads,
        expires_at=expires_at,
    )


@app.post("/convert/url", response_model=ImageResponse)
async def convert_url_to_image_endpoint(
    request: URLRequest, credentials: HTTPAuthorizationCredentials = Depends(security)
):
    verify_token_from_credentials(credentials)
    cleanup_old_images()  # Clean up on each request

    image_id = str(uuid.uuid4())
    image_path = str(STATIC_DIR / f"{image_id}.png")

    options = {
        "format": "png",
        "quiet": "",
        "quality": 85,
    }

    try:
        imgkit.from_url(str(request.url), image_path, options=options)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert URL to image: {str(e)}",
        )

    # Set expiry date
    expires_at = datetime.now() + timedelta(days=IMAGE_EXPIRY_DAYS)
    # max_downloads = (
    #     request.max_downloads if request.max_downloads is not None else MAX_DOWNLOADS
    # )
    max_downloads = MAX_DOWNLOADS

    # Store metadata
    image_metadata[image_id] = {
        "downloads_remaining": max_downloads,
        "expires_at": expires_at,
        "created_at": datetime.now(),
    }

    # Generate absolute URL for response
    image_url = get_absolute_url(f"/download/{image_id}?host_images={HOST_IMAGES}")

    return ImageResponse(
        image_url=image_url,
        image_id=image_id,
        downloads_remaining=max_downloads,
        expires_at=expires_at,
    )


@app.get("/download/{image_id}")
async def download_image(image_id: str, host_images: int = HOST_IMAGES):
    if image_id not in image_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found or expired",
        )

    image_path = STATIC_DIR / f"{image_id}.png"
    if not image_path.exists():
        # Clean up metadata if file is missing
        image_metadata.pop(image_id, None)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found",
        )

    # Check and update downloads remaining
    metadata = image_metadata[image_id]
    if metadata["downloads_remaining"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maximum number of downloads reached",
        )

    # Decrement downloads counter
    metadata["downloads_remaining"] -= 1

    # If downloads exhausted, schedule for removal
    if metadata["downloads_remaining"] <= 0:
        pass  # Will be removed on next cleanup

    # Handle download vs inline view
    content_disposition = "attachment" if host_images != 1 else "inline"

    return FileResponse(
        path=image_path,
        filename=f"{image_id}.png",
        media_type="image/png",
        headers={
            "Content-Disposition": f'{content_disposition}; filename="{image_id}.png"'
        },
    )


@app.get("/status/{image_id}")
async def get_image_status(
    image_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)
):
    verify_token_from_credentials(credentials)

    if image_id not in image_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found or expired",
        )

    metadata = image_metadata[image_id]
    download_url = get_absolute_url(f"/download/{image_id}")

    return JSONResponse(
        {
            "image_id": image_id,
            "image_url": download_url,
            "downloads_remaining": metadata["downloads_remaining"],
            "expires_at": metadata["expires_at"].isoformat(),
            "created_at": metadata["created_at"].isoformat(),
        }
    )


# Root endpoint for health check
@app.get("/")
async def root():
    return {"status": "ok", "service": "HTML to Image API"}


# Main entry point
if __name__ == "__main__":
    import uvicorn

    # Create static directory if it doesn't exist
    os.makedirs(STATIC_DIR, exist_ok=True)

    # Start server
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
