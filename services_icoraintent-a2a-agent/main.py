import os
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import SimpleMCPAgentExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize agent executor for JSON-RPC calls
json_rpc_agent_executor = SimpleMCPAgentExecutor()

def parse_jsonrpc_message(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON-RPC message"""
    try:
        # Validate JSON-RPC format
        if request_data.get("jsonrpc") != "2.0":
            raise ValueError("Invalid JSON-RPC version")
        
        if "id" not in request_data:
            raise ValueError("Missing required 'id' field")
        
        if "method" not in request_data:
            raise ValueError("Missing required 'method' field")
        
        method = request_data["method"]
        params = request_data.get("params", {})
        
        return {
            "id": request_data["id"],
            "method": method,
            "params": params
        }
    except Exception as e:
        raise ValueError(f"Invalid JSON-RPC message format: {str(e)}")

def create_jsonrpc_response(request_id: str, result: Any = None, error: Any = None) -> Dict[str, Any]:
    """Create JSON-RPC response"""
    response = {
        "jsonrpc": "2.0",
        "id": request_id
    }
    
    if error:
        response["error"] = {
            "code": -32600,
            "message": "Request payload validation error",
            "data": error
        }
    else:
        response["result"] = result
    
    return response

def create_a2a_task_result(task_id: str, content: Any, status: str = "completed") -> Dict[str, Any]:
    """Create A2A task result format"""
    # Ensure content is properly structured
    if isinstance(content, dict):
        formatted_content = content
    else:
        formatted_content = {
            "response": content,
            "type": "agent_response"
        }
    
    return {
        "artifacts": [
            {
                "artifactId": str(uuid.uuid4()),
                "name": "intent_response",
                "parts": [
                    {
                        "kind": "json",
                        "data": formatted_content
                    }
                ]
            }
        ],
        "contextId": str(uuid.uuid4()),
        "history": [],
        "id": task_id,
        "kind": "task",
        "status": {
            "state": status,
            "timestamp": datetime.utcnow().isoformat() + "+00:00"
        }
    }

async def process_jsonrpc_message(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Process JSON-RPC message and return result"""
    try:
        if method == "message/send":
            # Extract message from params
            message = params.get("message", {})
            parts = message.get("parts", [])
            
            if not parts:
                raise ValueError("No message parts found")
            
            # Get text content
            text_content = ""
            for part in parts:
                if "text" in part:
                    text_content += part["text"] + " "
            
            text_content = text_content.strip()
            
            if not text_content:
                raise ValueError("No text content found in message parts")
            
            # Create task ID
            task_id = str(uuid.uuid4())
            
            # Initialize agent if needed
            if json_rpc_agent_executor.agent is None:
                json_rpc_agent_executor._init_agent()
            
            # Create a simple context for processing
            from google.genai import types
            
            content = types.Content(role='user', parts=[types.Part(text=text_content)])
            
            # Get or create session
            session = await json_rpc_agent_executor.runner.session_service.get_session(
                app_name=json_rpc_agent_executor.runner.app_name,
                user_id='json_rpc_user',
                session_id=task_id,
            )
            
            if session is None:
                session = await json_rpc_agent_executor.runner.session_service.create_session(
                    app_name=json_rpc_agent_executor.runner.app_name,
                    user_id='json_rpc_user',
                    session_id=task_id,
                )
            
            # Process with agent
            final_result = None
            async for event in json_rpc_agent_executor.runner.run_async(
                session_id=session.id, 
                user_id='json_rpc_user', 
                new_message=content
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        response_text = '\n'.join([p.text for p in event.content.parts if p.text])
                        
                        # Try to parse as JSON if it looks like structured data
                        try:
                            if response_text.strip().startswith('{'):
                                final_result = json.loads(response_text)
                            else:
                                final_result = {
                                    "status": "success",
                                    "message": response_text,
                                    "response_type": "text"
                                }
                        except json.JSONDecodeError:
                            final_result = {
                                "status": "success",
                                "message": response_text,
                                "response_type": "text"
                            }
                    break
            
            if final_result is None:
                final_result = {
                    "status": "error",
                    "message": "Processing completed but no result returned"
                }
            
            # Create A2A task result
            task_result = create_a2a_task_result(task_id, final_result)
            return task_result
            
        else:
            raise ValueError(f"Unsupported method: {method}")
            
    except Exception as e:
        logger.error(f"Error processing JSON-RPC message: {str(e)}")
        raise

async def jsonrpc_endpoint(request: Request) -> JSONResponse:
    """Handle JSON-RPC requests"""
    try:
        request_data = await request.json()
        
        # Parse JSON-RPC message
        parsed = parse_jsonrpc_message(request_data)
        
        # Process message
        try:
            result = await process_jsonrpc_message(parsed["method"], parsed["params"])
            response_data = create_jsonrpc_response(parsed["id"], result)
        except Exception as e:
            error_data = [{
                "type": "processing_error",
                "message": str(e),
                "input": request_data
            }]
            response_data = create_jsonrpc_response(parsed["id"], error=error_data)
        
        return JSONResponse(response_data)
        
    except ValueError as e:
        # JSON-RPC validation error
        error_data = [{
            "type": "validation_error", 
            "message": str(e),
            "input": await request.json() if request.headers.get('content-type') == 'application/json' else {}
        }]
        response_data = create_jsonrpc_response("unknown", error=error_data)
        return JSONResponse(response_data)
    
    except Exception as e:
        logger.error(f"Unexpected error in JSON-RPC endpoint: {str(e)}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": "unknown",
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        }, status_code=500)

async def health_endpoint(request: Request) -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "Intent MCP Agent A2A",
        "timestamp": datetime.utcnow().isoformat() + "+00:00",
        "endpoints": {
            "jsonrpc": "/jsonrpc",
            "a2a": "/",
            "health": "/health"
        }
    })

# Check environment variables
if not os.getenv('GOOGLE_API_KEY'):
    raise ValueError('GOOGLE_API_KEY environment variable is required')

# Define agent skills
intent_creation_skill = AgentSkill(
    id='create_network_intent',
    name='Create Network Intent',
    description='Create network service intents for live events, video conferences, and data transfers.',
    tags=['Network', 'Intent', 'MCP'],
    examples=[
        'Create a 4K live broadcast intent for 1000 participants',
        'Set up a video conference intent for tomorrow',
        'Create a high-definition streaming intent'
    ],
)

status_check_skill = AgentSkill(
    id='check_system_status',
    name='Check System Status',
    description='Check MCP system health and connectivity.',
    tags=['Status', 'Health', 'Monitoring'],
    examples=[
        'Check if the MCP system is operational',
        'What is the current system status?'
    ],
)

workflow_test_skill = AgentSkill(
    id='test_workflow',
    name='Test Workflow',
    description='Test the complete MCP workflow including authentication.',
    tags=['Testing', 'Workflow'],
    examples=[
        'Run a complete system test',
        'Test the MCP workflow'
    ],
)

# Initialize A2A agent
agent_executor = SimpleMCPAgentExecutor()

# Get the service URL dynamically
SERVICE_URL = os.getenv('SERVICE_URL', 'https://{your_service_url}')

agent_card = AgentCard(
    name='Intent MCP Agent A2A',
    description='Network intent management agent using MCP cloud functions with both A2A and JSON-RPC support.',
    url=SERVICE_URL,  # Use full URL instead of '/'
    version='1.0.0',
    defaultInputModes=['text'],
    defaultOutputModes=['text'],
    capabilities=AgentCapabilities(streaming=True),
    skills=[intent_creation_skill, status_check_skill, workflow_test_skill],
)

request_handler = DefaultRequestHandler(
    agent_executor=agent_executor, 
    task_store=InMemoryTaskStore()
)

# Create A2A Starlette application
a2a_server = A2AStarletteApplication(agent_card, request_handler)
a2a_app = a2a_server.build()

# Create custom Starlette app with additional JSON-RPC endpoint
routes = [
    Route('/jsonrpc', jsonrpc_endpoint, methods=['POST']),
    Route('/health', health_endpoint, methods=['GET']),
    # Mount A2A app at root for A2A protocol
    Route('/{path:path}', a2a_app, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']),
]

middleware = [
    Middleware(CORSMiddleware, 
              allow_origins=['*'],
              allow_methods=['*'], 
              allow_headers=['*'])
]

# Create the main Starlette app
starlette_app = Starlette(routes=routes, middleware=middleware)

logger.info('Intent MCP Agent A2A ready with JSON-RPC support')
logger.info('Endpoints:')
logger.info('  - A2A Protocol: /')
logger.info('  - JSON-RPC: /jsonrpc')
logger.info('  - Health: /health')
logger.info(f'MCP Function URL: {os.getenv("MCP_FUNCTION_URL", "Not set")}')
logger.info(f'WireMock Function URL: {os.getenv("WIREMOCK_FUNCTION_URL", "Not set")}')

# Export the app for uvicorn
app = starlette_app