"""
iCORA intent MCP Server as Google Cloud Function using FastMCP
Serverless FastMCP implementation for iCORA Intent Management
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List

import httpx
from mcp.server.fastmcp import FastMCP
import functions_framework

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP instance
mcp = FastMCP("iCORA Intent TMF921 Cloud Intent Management")

# Configuration from environment variables
WIREMOCK_FUNCTION_URL = os.getenv('WIREMOCK_FUNCTION_URL', 'https://YOUR_WIREMOCK_FUNCTION_URL')
OAUTH_CLIENT_ID = os.getenv('OAUTH_CLIENT_ID', 'test-client')
OAUTH_CLIENT_SECRET = os.getenv('OAUTH_CLIENT_SECRET', 'test-secret')
OAUTH_USERNAME = os.getenv('OAUTH_USERNAME', 'test-user')
OAUTH_PASSWORD = os.getenv('OAUTH_PASSWORD', 'test-password')

# Global state for cloud function
token_manager: Optional['CloudTokenManager'] = None
base_url: str = ""

class CloudTokenManager:
    """Manages OAuth2 token acquisition and refresh for cloud deployment"""
    
    def __init__(self, auth_config: Dict[str, str]):
        self.auth_config = auth_config
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        
    async def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary"""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token
        await self._refresh_access_token()
        return self.token
        
    async def _refresh_access_token(self) -> None:
        """Acquire access token using password grant from cloud WireMock"""
        data = {
            'grant_type': 'password',
            'username': self.auth_config['username'],
            'password': self.auth_config['password'],
            'client_id': self.auth_config['client_id'],
            'client_secret': self.auth_config['client_secret'],
        }
        if 'scope' in self.auth_config:
            data['scope'] = self.auth_config['scope']
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                logger.info(f"Requesting token from: {self.auth_config['token_url']}")
                response = await client.post(
                    self.auth_config['token_url'],
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                )
                response.raise_for_status()
                token_data = response.json()
                self.token = token_data['access_token']
                expires_in = token_data.get('expires_in', 3600) - 30
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
                logger.info("✅ Cloud OAuth2 token acquired successfully")
            except Exception as e:
                logger.error(f"❌ Cloud authentication failed: {str(e)}")
                raise Exception(f"Cloud authentication failed: {str(e)}")

@mcp.tool()
def icoraintent_configure_cloud_auth(
    wiremockUrl: str = WIREMOCK_FUNCTION_URL,
    clientId: str = OAUTH_CLIENT_ID,
    clientSecret: str = OAUTH_CLIENT_SECRET,
    username: str = OAUTH_USERNAME,
    password: str = OAUTH_PASSWORD,
    scope: str = None
) -> str:
    """Configure iCORA Intent TMF921 API authentication for cloud deployment"""
    global token_manager, base_url
    
    try:
        # Build token URL from WireMock function URL
        token_url = f"{wiremockUrl}/auth/keycloak_realm/protocol/openid-connect/token"
        
        auth_config = {
            'token_url': token_url,
            'client_id': clientId,
            'client_secret': clientSecret,
            'username': username,
            'password': password,
        }
        if scope:
            auth_config['scope'] = scope
            
        base_url = wiremockUrl
        token_manager = CloudTokenManager(auth_config)
        
        logger.info(f"✅ Configured for cloud WireMock at: {wiremockUrl}")
        return f"✅ iCORA Intent TMF921 cloud authentication configured for: {wiremockUrl}"
        
    except Exception as e:
        logger.error(f"❌ Cloud configuration error: {str(e)}")
        return f"❌ Cloud configuration error: {str(e)}"

@mcp.tool()
async def icoraintent_test_cloud_auth() -> str:
    """Test iCORA Intent API authentication against cloud WireMock"""
    global token_manager
    
    try:
        if not token_manager:
            return "❌ Cloud authentication not configured. Use icoraintent_configure_cloud_auth first."
            
        token = await token_manager.get_valid_token()
        return f"✅ Cloud authentication successful! Token: {token[:20]}..."
        
    except Exception as e:
        logger.error(f"❌ Cloud authentication test failed: {str(e)}")
        return f"❌ Cloud authentication test failed: {str(e)}"

@mcp.tool()
async def icoraintent_create_cloud_intent(
    name: str,
    description: str,
    intentType: str = "EventLiveBroadcast",
    deliveryExpectations: List[Dict] = None,
    serviceArea: List[Dict] = None,
    validFor: Dict = None,
    propertyExpectations: List[Dict] = None
) -> str:
    """Create a new intent in cloud icora intent system"""
    global token_manager, base_url
    
    try:
        if not token_manager:
            return "❌ Cloud authentication not configured. Use icoraintent_configure_cloud_auth first."
            
        # Set default delivery expectations if none provided
        if not deliveryExpectations:
            deliveryExpectations = [
                {
                    "target": "_:service",
                    "params": {
                        "targetDescription": "cat:EventWirelessAccess"
                    }
                }
            ]
            
        token = await token_manager.get_valid_token()
        intent_payload = _build_cloud_intent_payload({
            "name": name,
            "description": description,
            "intentType": intentType,
            "deliveryExpectations": deliveryExpectations,
            "serviceArea": serviceArea,
            "validFor": validFor,
            "propertyExpectations": propertyExpectations
        })
        
        intent_url = f"{base_url}/intent/"
        logger.info(f"Creating intent at: {intent_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                intent_url,
                json=intent_payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }
            )
            
            if response.status_code == 201:
                result = response.json()
                location = response.headers.get('location', 'N/A')
                logger.info("✅ Cloud intent created successfully")
                return f"""✅ Cloud intent created successfully!
📍 Location: {location}
📄 Response: {json.dumps(result, indent=2)}"""
            else:
                logger.error(f"❌ Cloud intent creation failed: {response.status_code}")
                return f"❌ Cloud intent creation failed: {response.status_code} - {response.text}"
                
    except Exception as e:
        logger.error(f"❌ Error creating cloud intent: {str(e)}")
        return f"❌ Error creating cloud intent: {str(e)}"

@mcp.tool()
async def check_cloud_connectivity() -> str:
    """Check connectivity to cloud WireMock function"""
    try:
        if not base_url:
            # Use default URL if not configured yet
            test_url = WIREMOCK_FUNCTION_URL
        else:
            test_url = base_url
            
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test basic connectivity
            health_url = f"{test_url}/health"
            response = await client.get(health_url)
            
            if response.status_code == 200:
                # Check admin endpoint
                admin_url = f"{test_url}/__admin/mappings"
                admin_response = await client.get(admin_url)
                
                if admin_response.status_code == 200:
                    mappings = admin_response.json().get('mappings', [])
                    return f"✅ Cloud WireMock function fully accessible! {len(mappings)} mappings loaded at {test_url}"
                else:
                    return f"⚠️  Cloud WireMock function responding but admin not accessible at {test_url}"
            else:
                return f"❌ Cloud WireMock function not responding at {test_url}"
                
    except Exception as e:
        return f"❌ Cannot reach cloud WireMock function: {str(e)}"

@mcp.tool()
def cloud_health_check() -> str:
    """Check if the cloud icora intentMCP server is healthy"""
    return f"✅ icora intentTMF921 Cloud FastMCP Function is healthy! WireMock: {base_url or WIREMOCK_FUNCTION_URL}"

@mcp.tool()
async def list_cloud_tools() -> str:
    """List all available cloud tools"""
    tools = [
        "icoraintent_configure_cloud_auth - Configure authentication for cloud WireMock",
        "icoraintent_test_cloud_auth - Test cloud authentication",
        "icoraintent_create_cloud_intent - Create network intent via cloud",
        "check_cloud_connectivity - Check cloud WireMock connectivity",
        "cloud_health_check - Check this MCP function health",
        "list_cloud_tools - List all available tools"
    ]
    return f"✅ Available cloud tools:\n" + "\n".join(f"• {tool}" for tool in tools)

def _build_cloud_intent_payload(arguments: Dict) -> Dict:
    """Build TMF921 compliant intent payload for cloud deployment"""
    payload = {
        "name": arguments["name"],
        "description": arguments["description"],
        "type": "Intent",
        "deliveryExpectations": arguments["deliveryExpectations"]
    }
    
    if arguments.get("validFor"):
        payload["validFor"] = arguments["validFor"]
        
    if arguments.get("propertyExpectations"):
        payload["propertyExpectations"] = arguments["propertyExpectations"]
        
    # Build JSON-LD structure for EventLiveBroadcast
    if arguments.get("intentType") == "EventLiveBroadcast":
        payload["expression"] = {
            "context": {
                "icm": "http://www.models.tmforum.org/tio/v1.0/IntentCommonModel#",
                "cat": "http://www.operator.com/Catalog#",
                "idan": "http://www.idan-tmforum-catalyst.org/IntentDrivenAutonomousNetworks#",
                "geo": "https://tmforum.org/2020/07/geographicPoint#"
            },
            "idan": {
                "EventLiveBroadcast": {
                    "@type": "icm:Intent",
                    "icm:intentOwner": "idan:ABCEvents",
                    "icm:hasExpectation": []
                }
            }
        }
        
        # Add service area if provided
        if arguments.get("serviceArea"):
            geo_points = [
                {
                    "geo:longitude": point["longitude"],
                    "geo:latitude": point["latitude"]
                }
                for point in arguments["serviceArea"]
            ]
            
            if "propertyExpectations" not in payload:
                payload["propertyExpectations"] = []
            payload["propertyExpectations"].append({
                "target": "_:service",
                "params": {
                    "elb:areaOfService": geo_points
                }
            })
                
    return payload

# Initialize with environment variables on cold start
def _initialize_from_env():
    """Initialize configuration from environment variables"""
    global token_manager, base_url
    
    if WIREMOCK_FUNCTION_URL and WIREMOCK_FUNCTION_URL != 'https://YOUR_WIREMOCK_FUNCTION_URL':
        try:
            token_url = f"{WIREMOCK_FUNCTION_URL}/auth/keycloak_realm/protocol/openid-connect/token"
            auth_config = {
                'token_url': token_url,
                'client_id': OAUTH_CLIENT_ID,
                'client_secret': OAUTH_CLIENT_SECRET,
                'username': OAUTH_USERNAME,
                'password': OAUTH_PASSWORD,
            }
            base_url = WIREMOCK_FUNCTION_URL
            token_manager = CloudTokenManager(auth_config)
            logger.info(f"✅ Auto-configured from environment: {WIREMOCK_FUNCTION_URL}")
        except Exception as e:
            logger.warning(f"⚠️  Auto-configuration failed: {str(e)}")

# Auto-initialize on import
_initialize_from_env()

# Google Cloud Functions entry point
@functions_framework.http
def icoraintent_mcp_function(request):
    """Cloud Function entry point for FastMCP server"""
    import asyncio
    import json
    from urllib.parse import parse_qs
    
    try:
        # Handle different HTTP methods
        if request.method == 'GET':
            if request.path == '/health':
                return {
                    "status": "healthy",
                    "service": "icoraintent-fastmcp-function",
                    "timestamp": datetime.utcnow().isoformat(),
                    "wiremock_url": base_url or WIREMOCK_FUNCTION_URL
                }, 200
            elif request.path == '/':
                return {
                    "service": "icora intentTMF921 FastMCP Cloud Function",
                    "version": "1.0.0",
                    "status": "ready",
                    "tools_available": 6
                }, 200
        
        # For MCP JSON-RPC requests
        if request.method == 'POST':
            try:
                # Get request data
                if request.content_type == 'application/json':
                    request_data = request.get_json()
                else:
                    request_data = json.loads(request.data.decode('utf-8'))
                
                # Handle MCP initialize
                if request_data.get('method') == 'initialize':
                    return {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id", 1),
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {}},
                            "serverInfo": {
                                "name": "icora intentTMF921 Cloud FastMCP",
                                "version": "1.0.0"
                            }
                        }
                    }, 200
                
                # Handle MCP tools/list
                if request_data.get('method') == 'tools/list':
                    tools = [
                        {
                            "name": "icoraintent_configure_cloud_auth",
                            "description": "Configure icora intentTMF921 API authentication for cloud",
                            "inputSchema": {"type": "object", "properties": {
                                "wiremockUrl": {"type": "string"},
                                "clientId": {"type": "string"},
                                "clientSecret": {"type": "string"},
                                "username": {"type": "string"},
                                "password": {"type": "string"}
                            }}
                        },
                        {
                            "name": "icoraintent_test_cloud_auth",
                            "description": "Test icora intentAPI cloud authentication",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "icoraintent_create_cloud_intent",
                            "description": "Create a new icora intentnetwork intent via cloud",
                            "inputSchema": {"type": "object", "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "intentType": {"type": "string"},
                                "deliveryExpectations": {"type": "array"},
                                "serviceArea": {"type": "array"},
                                "validFor": {"type": "object"},
                                "propertyExpectations": {"type": "array"}
                            }, "required": ["name", "description"]}
                        },
                        {
                            "name": "check_cloud_connectivity",
                            "description": "Check connectivity to cloud WireMock function",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "cloud_health_check",
                            "description": "Check cloud MCP function health",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        {
                            "name": "list_cloud_tools",
                            "description": "List all available cloud tools",
                            "inputSchema": {"type": "object", "properties": {}}
                        }
                    ]
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id", 1),
                        "result": {"tools": tools}
                    }, 200
                
                # Handle MCP tools/call
                if request_data.get('method') == 'tools/call':
                    tool_name = request_data["params"]["name"]
                    arguments = request_data["params"].get("arguments", {})
                    
                    # Map tool calls to FastMCP functions
                    if tool_name == "icoraintent_configure_cloud_auth":
                        result = icoraintent_configure_cloud_auth(**arguments)
                    elif tool_name == "icoraintent_test_cloud_auth":
                        result = asyncio.run(icoraintent_test_cloud_auth())
                    elif tool_name == "icoraintent_create_cloud_intent":
                        result = asyncio.run(icoraintent_create_cloud_intent(**arguments))
                    elif tool_name == "check_cloud_connectivity":
                        result = asyncio.run(check_cloud_connectivity())
                    elif tool_name == "cloud_health_check":
                        result = cloud_health_check()
                    elif tool_name == "list_cloud_tools":
                        result = asyncio.run(list_cloud_tools())
                    else:
                        return {
                            "jsonrpc": "2.0",
                            "id": request_data.get("id", 1),
                            "error": {
                                "code": -32601,
                                "message": f"Tool not found: {tool_name}"
                            }
                        }, 404
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id", 1),
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": result
                            }]
                        }
                    }, 200
                
            except Exception as e:
                logger.error(f"❌ MCP request error: {str(e)}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id", 1) if 'request_data' in locals() else 1,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }, 500
        
        # Default response
        return {
            "error": "method_not_allowed",
            "message": "Only GET /health and POST for MCP are supported"
        }, 405
        
    except Exception as e:
        logger.error(f"❌ Function error: {str(e)}")
        return {
            "error": "internal_server_error",
            "error_description": str(e)
        }, 500

# For local development
if __name__ == "__main__":
    logger.info("🌩️  Starting icora intent FastMCP Cloud Function locally...")
    mcp.run()