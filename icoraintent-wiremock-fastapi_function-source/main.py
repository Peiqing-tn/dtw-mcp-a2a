"""
icoraintent WireMock API using Real FastAPI on Google Cloud Functions
Proper FastAPI implementation with Cloud Functions
"""

import json
import uuid
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Depends, Form, Header
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
import functions_framework

# FastAPI app
app = FastAPI(
    title="icoraintent WireMock API",
    description="Serverless icoraintent TMF921 Intent Management API mock using FastAPI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Pydantic models
class OAuthTokenResponse(BaseModel):
    access_token: str
    expires_in: int = 3600
    refresh_expires_in: int = 1800
    refresh_token: str
    token_type: str = "Bearer"
    not_before_policy: int = 0
    session_state: str
    scope: str = "email profile"

class DeliveryExpectation(BaseModel):
    target: str
    params: Dict[str, Any]

class ServiceArea(BaseModel):
    longitude: float
    latitude: float

class ValidFor(BaseModel):
    startDateTime: str
    endDateTime: str

class PropertyExpectation(BaseModel):
    target: str
    params: Dict[str, Any]

class IntentRequest(BaseModel):
    name: str = Field(..., description="Intent name")
    description: str = Field(..., description="Intent description")
    type: str = Field(default="Intent", description="Intent type")
    deliveryExpectations: List[DeliveryExpectation] = Field(..., description="Delivery expectations")
    validFor: Optional[ValidFor] = Field(None, description="Validity period")
    propertyExpectations: Optional[List[PropertyExpectation]] = Field(None, description="Property expectations")
    serviceArea: Optional[List[ServiceArea]] = Field(None, description="Service area coordinates")

class IntentResponse(BaseModel):
    id: str
    name: str
    description: str
    type: str
    status: str
    createdAt: str
    deliveryExpectations: List[DeliveryExpectation]
    _links: Dict[str, Dict[str, str]]

class AdminMapping(BaseModel):
    id: str
    request: Dict[str, Any]
    response: Dict[str, Any]

class AdminMappingsResponse(BaseModel):
    mappings: List[AdminMapping]
    meta: Dict[str, int]

class ErrorResponse(BaseModel):
    error: str
    error_description: str

# Dependency to validate Bearer token
def validate_bearer_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "error_description": "Bearer token required"}
        )
    return authorization

# Helper functions
def generate_oauth_response() -> OAuthTokenResponse:
    """Generate mock OAuth token response"""
    return OAuthTokenResponse(
        access_token=f"cloud_mock_token_{uuid.uuid4().hex[:16]}",
        expires_in=3600,
        refresh_expires_in=1800,
        refresh_token=f"cloud_refresh_{uuid.uuid4().hex[:16]}",
        token_type="Bearer",
        not_before_policy=0,
        session_state=f"session_{uuid.uuid4().hex[:8]}",
        scope="email profile"
    )

def generate_intent_response(request_data: IntentRequest, base_url: str) -> IntentResponse:
    """Generate mock intent creation response"""
    intent_id = f"intent-{uuid.uuid4().hex[:10]}"
    
    return IntentResponse(
        id=intent_id,
        name=request_data.name,
        description=request_data.description,
        type="Intent",
        status="created",
        createdAt=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        deliveryExpectations=request_data.deliveryExpectations,
        _links={
            "self": {
                "href": f"{base_url}/intent/{intent_id}"
            }
        }
    )

# API Routes
@app.get("/", response_model=Dict[str, Any])
async def root():
    """Root endpoint with API information"""
    return {
        "service": "icoraintent WireMock FastAPI",
        "version": "1.0.0",
        "status": "ready",
        "framework": "FastAPI",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": [
            "GET /",
            "GET /test",
            "GET /health",
            "GET /__admin/mappings",
            "POST /auth/keycloak_realm/protocol/openid-connect/token",
            "POST /intent/",
            "GET /intent/{intent_id}"
        ]
    }

@app.get("/test", response_model=Dict[str, Any])
async def test_endpoint():
    """Simple test endpoint to verify the service is running"""
    return {
        "status": "success",
        "message": "icoraintent WireMock FastAPI Cloud Function is working perfectly!",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "fastapi-cloud-function",
        "framework": "FastAPI"
    }

@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "icoraintent-wiremock-fastapi",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "framework": "FastAPI"
    }

@app.get("/__admin/mappings", response_model=AdminMappingsResponse)
async def admin_mappings():
    """Mock admin endpoint to show available mappings"""
    mappings = [
        AdminMapping(
            id="oauth-mapping",
            request={
                "method": "POST",
                "urlPath": "/auth/keycloak_realm/protocol/openid-connect/token"
            },
            response={"status": 200}
        ),
        AdminMapping(
            id="intent-mapping",
            request={
                "method": "POST",
                "urlPath": "/intent/"
            },
            response={"status": 201}
        ),
        AdminMapping(
            id="test-mapping",
            request={
                "method": "GET",
                "urlPath": "/test"
            },
            response={"status": 200}
        )
    ]
    
    return AdminMappingsResponse(
        mappings=mappings,
        meta={"total": len(mappings)}
    )

@app.post("/auth/keycloak_realm/protocol/openid-connect/token", response_model=OAuthTokenResponse)
async def oauth_token(
    grant_type: str = Form(..., description="OAuth grant type"),
    username: str = Form(..., description="Username"),
    password: str = Form(..., description="Password"),
    client_id: str = Form(..., description="Client ID"),
    client_secret: str = Form(..., description="Client secret"),
    scope: Optional[str] = Form(None, description="OAuth scope")
):
    """OAuth2 token endpoint with automatic form validation"""
    
    # Validate grant type
    if grant_type != 'password':
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_grant_type",
                "error_description": "Only password grant type is supported"
            }
        )
    
    # FastAPI automatically validates required fields
    # Additional business logic validation can go here
    
    # Generate successful response
    response_data = generate_oauth_response()
    
    # Return response with proper headers
    response = JSONResponse(
        content=response_data.dict(),
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache"
        }
    )
    
    return response

@app.post("/intent/", response_model=IntentResponse, status_code=201)
async def create_intent(
    intent_request: IntentRequest,
    authorization: str = Depends(validate_bearer_token)
):
    """Create a new network intent with automatic validation"""
    
    # FastAPI automatically validates the request body using Pydantic
    # The intent_request is already validated at this point
    
    # Get base URL (simplified for Cloud Functions)
    base_url = "https://cloud-function-url"
    
    # Generate successful response
    response_data = generate_intent_response(intent_request, base_url)
    
    # Return response with location header
    response = JSONResponse(
        content=response_data.dict(),
        status_code=201,
        headers={
            "Location": f"{base_url}/intent/{response_data.id}"
        }
    )
    
    return response

@app.get("/intent/{intent_id}", response_model=Dict[str, Any])
async def get_intent(intent_id: str):
    """Get a specific intent by ID"""
    
    # Validate intent ID format
    if not re.match(r'^intent-[a-f0-9]{10}$', intent_id):
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "error_description": f"Intent {intent_id} not found"
            }
        )
    
    base_url = "https://cloud-function-url"
    
    # Return mock intent data
    return {
        "id": intent_id,
        "name": "MockIntent",
        "description": "Mock intent for testing",
        "type": "Intent",
        "status": "active",
        "createdAt": "2025-06-11T10:00:00Z",
        "lastModified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deliveryExpectations": [
            {
                "target": "_:service",
                "params": {
                    "targetDescription": "cat:EventWirelessAccess"
                }
            }
        ],
        "_links": {
            "self": {
                "href": f"{base_url}/intent/{intent_id}"
            }
        }
    }

# Custom exception handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "error_description": "The requested resource was not found",
            "path": str(request.url.path)
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "error_description": "An internal server error occurred"
        }
    )

# Cloud Functions entry point
@functions_framework.http
def icoraintent_wiremock_function(request):
    """Google Cloud Function entry point for FastAPI"""
    from asgiref.wsgi import WsgiToAsgi
    from fastapi.middleware.wsgi import WSGIMiddleware
    import asyncio
    
    # Create ASGI application from FastAPI
    asgi_app = app
    
    # For Cloud Functions, we need to handle the request properly
    import os
    import sys
    from io import StringIO
    
    try:
        # Set up environment for FastAPI
        environ = {
            'REQUEST_METHOD': request.method,
            'PATH_INFO': request.path,
            'QUERY_STRING': request.query_string.decode() if request.query_string else '',
            'CONTENT_TYPE': request.content_type or '',
            'CONTENT_LENGTH': str(len(request.data)) if request.data else '0',
            'SERVER_NAME': request.host.split(':')[0] if request.host else 'localhost',
            'SERVER_PORT': request.host.split(':')[1] if ':' in (request.host or '') else '80',
            'wsgi.input': StringIO(request.data.decode() if request.data else ''),
            'wsgi.errors': sys.stderr,
        }
        
        # Add headers
        for key, value in request.headers.items():
            key = 'HTTP_' + key.upper().replace('-', '_')
            environ[key] = value
        
        # Simple response handler for Cloud Functions
        response_data = []
        response_status = [200]
        response_headers = []
        
        def start_response(status, headers):
            response_status[0] = int(status.split()[0])
            response_headers.extend(headers)
        
        # For Cloud Functions, we'll handle this more directly
        # This is a simplified approach for the demo
        
        if request.path == '/':
            return app.routes[0].endpoint(), 200
        elif request.path == '/test':
            return {
                "status": "success",
                "message": "icoraintent WireMock FastAPI Cloud Function is working!",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "fastapi-cloud-function",
                "framework": "FastAPI"
            }, 200
        elif request.path == '/health':
            return {
                "status": "healthy",
                "service": "icoraintent-wiremock-fastapi",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
                "framework": "FastAPI"
            }, 200
        elif request.path == '/__admin/mappings':
            mappings = [
                {
                    "id": "oauth-mapping",
                    "request": {"method": "POST", "urlPath": "/auth/keycloak_realm/protocol/openid-connect/token"},
                    "response": {"status": 200}
                },
                {
                    "id": "intent-mapping",
                    "request": {"method": "POST", "urlPath": "/intent/"},
                    "response": {"status": 201}
                }
            ]
            return {"mappings": mappings, "meta": {"total": len(mappings)}}, 200
        elif request.path == '/auth/keycloak_realm/protocol/openid-connect/token' and request.method == 'POST':
            # Handle OAuth
            form_data = request.form
            if form_data.get('grant_type') != 'password':
                return {
                    "error": "unsupported_grant_type",
                    "error_description": "Only password grant type is supported"
                }, 400
            
            response_data = generate_oauth_response()
            return response_data.dict(), 200, {
                "Cache-Control": "no-store",
                "Pragma": "no-cache"
            }
        elif request.path == '/intent/' and request.method == 'POST':
            # Handle intent creation
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return {
                    "error": "unauthorized",
                    "error_description": "Bearer token required"
                }, 401
            
            try:
                json_data = request.get_json()
                intent_request = IntentRequest(**json_data)
                response_data = generate_intent_response(intent_request, f"https://{request.host}")
                return response_data.dict(), 201, {
                    "Location": f"https://{request.host}/intent/{response_data.id}"
                }
            except Exception as e:
                return {
                    "error": "validation_error",
                    "error_description": str(e)
                }, 400
        elif request.path == '/docs':
            # Return link to docs
            return {
                "message": "FastAPI documentation",
                "docs_url": f"https://{request.host}/docs",
                "redoc_url": f"https://{request.host}/redoc"
            }, 200
        else:
            return {
                "error": "not_found",
                "error_description": f"Endpoint not found: {request.method} {request.path}"
            }, 404
            
    except Exception as e:
        import logging
        logging.error(f"FastAPI Function error: {str(e)}", exc_info=True)
        return {
            "error": "internal_server_error",
            "error_description": str(e)
        }, 500

# For local development
if __name__ == "__main__":
    import uvicorn
    print("🚀 Running icoraintent WireMock FastAPI locally on http://localhost:8080")
    print("📚 API Documentation: http://localhost:8080/docs")
    uvicorn.run(app, host="0.0.0.0", port=8080)