import logging
import datetime
import json
import random
import requests
import os
from typing import Dict, Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError
from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService
from google.genai import types
from a2a.utils import new_agent_text_message

logger = logging.getLogger(__name__)

# Configuration from environment
MCP_FUNCTION_URL = os.getenv('MCP_FUNCTION_URL', 'https://europe-north1-deep-ground-462419-k0.cloudfunctions.net/icoraintent-mcp-fastmcp')
WIREMOCK_FUNCTION_URL = os.getenv('WIREMOCK_FUNCTION_URL', 'https://europe-north1-deep-ground-462419-k0.cloudfunctions.net/icoraintent-wiremock-fastapi')

def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Call MCP Cloud Function tool via JSON-RPC"""
    try:
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = requests.post(
            MCP_FUNCTION_URL,
            json=mcp_request,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        if response.status_code == 200:
            mcp_response = response.json()
            if "result" in mcp_response:
                content = mcp_response["result"].get("content", [])
                if content:
                    result_text = content[0].get("text", "Success")
                    return {"status": "success", "result": result_text}
            elif "error" in mcp_response:
                error_msg = mcp_response["error"].get("message", "Unknown MCP error")
                return {"status": "error", "error_message": f"MCP Error: {error_msg}"}
        
        return {
            "status": "error", 
            "error_message": f"HTTP {response.status_code}: {response.text[:200]}"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error calling MCP function: {str(e)}"
        }

def get_current_datetime() -> dict:
    """Get current date and time"""
    now = datetime.datetime.now()
    return {
        "status": "success",
        "current_datetime": now.isoformat(),
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M:%S")
    }

def list_mcp_tools() -> dict:
    """List all available MCP tools"""
    result = call_mcp_tool("list_cloud_tools", {})
    return result

def check_mcp_status() -> dict:
    """Check MCP system status"""
    try:
        # Test health endpoint
        health_response = requests.get(f"{MCP_FUNCTION_URL}/health", timeout=10)
        if health_response.status_code == 200:
            return {
                "status": "success",
                "message": "MCP system is healthy and operational",
                "mcp_url": MCP_FUNCTION_URL
            }
        else:
            return {
                "status": "warning",
                "message": f"MCP system responded with status {health_response.status_code}",
                "mcp_url": MCP_FUNCTION_URL
            }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Cannot connect to MCP system: {str(e)}"
        }

def create_network_intent(
    name: str = "",
    description: str = "",
    intent_type: str = "EventLiveBroadcast",
    start_time: str = "",
    end_time: str = "",
    max_participants: int = 1000,
    quality: str = "HD",
    longitude: float = 0.0,
    latitude: float = 0.0
) -> dict:
    """Create a network service intent via MCP"""
    
    # Get current time for start/end times
    now = datetime.datetime.now()
    start_time = now.replace(hour=0, minute=0, second=0).isoformat()
    end_time = now.replace(hour=23, minute=59, second=59).isoformat()
    
    # Build MCP arguments
    arguments = {
        "name": name,
        "description": description,
        "intentType": intent_type,
        "validFor": {
            "startDateTime": start_time,
            "endDateTime": end_time
        }
    }

    
    # Create intent via MCP
    result = call_mcp_tool("icoraintent_create_cloud_intent", arguments)
    
    if result["status"] == "success":
        return {
            "status": "success",
            "intent_id": name,
            "message": f"Network intent '{name}' created successfully",
            "configuration": {
                "name": name,
                "description": description,
                "intent_type": intent_type,
                "start_time": start_time,
                "end_time": end_time,
                "intent_typ": intent_type,
                "quality": quality,
                "max_participants": max_participants,
                "coordinates": [longitude, latitude] if longitude != 0.0 or latitude != 0.0 else None
            },
            "mcp_result": result
        }
    else:
        return {
            "status": "error",
            "error_message": f"Failed to create intent: {result.get('error_message', 'Unknown error')}",
            "mcp_result": result
        }

def configure_mcp_auth() -> dict:
    """Configure MCP authentication"""
    result = call_mcp_tool("icoraintent_configure_cloud_auth", {
        "wiremockUrl": WIREMOCK_FUNCTION_URL,
        "clientId": "test-client",
        "clientSecret": "test-secret", 
        "username": "test-user",
        "password": "test-password"
    })
    return result

def test_mcp_workflow() -> dict:
    """Test complete MCP workflow"""
    try:
        # Step 1: Check status
        status_result = check_mcp_status()
        if status_result["status"] != "success":
            return {
                "status": "error",
                "error_message": "MCP system is not healthy",
                "step_failed": "status_check"
            }
        
        # Step 2: Configure auth
        auth_result = configure_mcp_auth()
        if auth_result["status"] != "success":
            return {
                "status": "error", 
                "error_message": "Authentication configuration failed",
                "step_failed": "auth_config"
            }
        
        # Step 3: Create test intent
        intent_result = create_network_intent(
            name="TestIntent",
            description="Test workflow intent",
            quality="4KUHD",
            max_participants=500
        )
        
        if intent_result["status"] == "success":
            return {
                "status": "success",
                "message": "Complete MCP workflow test passed",
                "test_intent_id": intent_result["intent_id"],
                "steps_completed": ["status_check", "auth_config", "intent_creation"]
            }
        else:
            return {
                "status": "error",
                "error_message": "Intent creation failed",
                "step_failed": "intent_creation"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Workflow test failed: {str(e)}"
        }

class SimpleMCPAgentExecutor(AgentExecutor):
    """Simplified MCP Agent Executor for A2A deployment."""

    def __init__(self):
        self.agent = None
        self.runner = None

    def _init_agent(self):
        self.agent = LlmAgent(
            model='gemini-2.0-flash-exp',
            name='simple_mcp_agent',
            description='A simplified network intent management agent using MCP cloud functions.',
            instruction="""You are a network intent management agent that creates network service intents using MCP cloud functions.

CRITICAL: NEVER ask users for missing parameters. ALWAYS use intelligent defaults and create the intent immediately.

Your capabilities:
1. Create network service intents (EventLiveBroadcast, VideoConference, DataTransfer)
2. Check MCP system status and health
3. Test the complete MCP workflow

        "Date handling:\n"
        "- if user does not specify a start date, use today's date as start date\n"
        "- if user does not specify an end date, use the next day of the start day as end date\n"
        "- you can use tool get_current_datetime\n"
  
        "Missing parameters:\n"
        "- if the user does not specify a name, use 'Intent' followed by a random number as name\n"
        "- if the user does not specify a description, use the message from user as description\n\n"
        "- If start time is not specified, use 00:00:00 (0 PM) as default\n"
        "- If end time is not specified, use 23:59:59 (11:59 PM) as default\n"
        "- If longitude/latitude are not specified, use 0.0 (no geographic constraints)\n"
        "- If quality is not specified, use 'HD' as default\n"
        "- If max participants are not specified, use 1000 as default\n\n"
        "- if intent type is not specified use EventLiveBroadcast\n"


        "Quality options: 4KUHD, HD, SD\n"
        "Coordinates: longitude/latitude as decimal degrees\n\n"0

Example user input: "Create a 4K live broadcast intent for 1000 participants"
Your action: IMMEDIATELY call create_network_intent(quality="4KUHD", max_participants=1000, description="Create a 4K live broadcast intent for 1000 participants")

Quality options: HD, 4KUHD, SD
Intent types: EventLiveBroadcast, VideoConference, DataTransfer""",
            tools=[
                get_current_datetime,
                list_mcp_tools,
                check_mcp_status,
                create_network_intent,
                configure_mcp_auth,
                test_mcp_workflow
            ],
        )
        self.runner = Runner(
            app_name=self.agent.name,
            agent=self.agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        if self.agent is None:
            self._init_agent()
        
        logger.debug(f'Executing agent {self.agent.name}')

        query = context.get_user_input()
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        if not context.current_task:
            await updater.submit()

        await updater.start_work()

        content = types.Content(role='user', parts=[types.Part(text=query)])
        session = await self.runner.session_service.get_session(
            app_name=self.runner.app_name,
            user_id='123',
            session_id=context.context_id,
        ) or await self.runner.session_service.create_session(
            app_name=self.runner.app_name,
            user_id='123',
            session_id=context.context_id,
        )

        try:
            async for event in self.runner.run_async(
                session_id=session.id, user_id='123', new_message=content
            ):
                logger.debug(f'Event from ADK {event}')
                if event.is_final_response():
                    parts = event.content.parts
                    text_parts = [
                        TextPart(text=part.text) for part in parts if part.text
                    ]
                    
                    await updater.add_artifact(
                        text_parts,
                        name='result',
                    )
                    await updater.complete()
                    break
                else:
                    await updater.update_status(
                        TaskState.working,
                        message=new_agent_text_message('Working...')
                    )
            else:
                logger.error('Agent failed to complete')
                await updater.update_status(
                    TaskState.failed,
                    message=new_agent_text_message('Failed to generate a response.'),
                )
                        
        except Exception as e:
            logger.error(f"Error during agent execution: {e}")
            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message(f'Error during execution: {str(e)}'),
            )