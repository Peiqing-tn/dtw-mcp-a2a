# iCORA Intent Management Project

This project contains a set of services for managing network intents, designed to be deployed as Google Cloud Functions. The system is composed of three main components: an A2A (Agent-to-Agent) agent, a mock TMF921 Intent Management API, and a serverless MCP (Multi-Cloud Platform) for intent management.

## Components

### 1. A2A Agent (`services_icoraintent-a2a-agent`)

This is the main entry point for interacting with the system. It's an A2A agent that provides a high-level interface for creating and managing network intents.

**Key Features:**

*   **Simplified Intent Creation:** Provides a simple interface for creating network intents without needing to know the details of the underlying APIs.
*   **Authentication:** Handles authentication with the MCP service.
*   **Workflow Management:** Can be used to orchestrate complex workflows involving multiple services.

### 2. Mock TMF921 Intent Management API (`icoraintent-wiremock-fastapi_function-source`)

This service is a mock implementation of the TMF921 Intent Management API. It's built with FastAPI and is designed to be deployed as a serverless function on Google Cloud.

**Key Features:**

*   **Intent API Mocking:** Simulates the behavior of a TMF921 API, allowing for realistic development and testing. Note: During the Hackathon the Nokia expert is on sick leave. There was no opportunity to fully undersand on Nokia's intent system. The API Mocking is not a 100% mapping of Nokia's intent API.
*   **FastAPI Backend:** Built with FastAPI, providing a robust and well-documented API.
*   **Serverless Deployment:** Designed to be deployed as a Google Cloud Function, making it easy to manage and scale.

### 3. Serverless MCP for Intent Management (`icoraintent-mcp-fastmcp_function-source`)

This service is a serverless implementation of an MCP for intent management. It's built with FastMCP and is designed to be deployed as a Google Cloud Function.

**Key Features:**

*   **Intent Management:** Provides a set of tools for managing network intents, including creating, updating, and deleting intents.
*   **Authentication:** Handles authentication with the underlying network services.
*   **Serverless Deployment:** Designed to be deployed as a Google Cloud Function, making it easy to manage and scale.

## Getting Started

To get started with this project, you'll need to deploy the three services to Google Cloud. The following sections provide instructions for deploying each service.

### Prerequisites

*   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
*   [Python 3.11+](https://www.python.org/downloads/)
*   [Rye](https://rye-up.com/guide/installation/)

### Deployment

#### 1. Mock TMF921 Intent Management API

```bash
cd icoraintent-wiremock-fastapi_function-source
gcloud functions deploy icoraintent-wiremock-fastapi --runtime python311 --trigger-http --allow-unauthenticated
```

#### 2. Serverless MCP for Intent Management

```bash
cd icoraintent-mcp-fastmcp_function-source
gcloud functions deploy icoraintent-mcp-fastmcp --runtime python311 --trigger-http --allow-unauthenticated
```

#### 3. A2A Agent

```bash
cd services_icoraintent-a2a-agent
rye sync
rye run deploy
```

## Usage

Once the services are deployed, you can interact with the system through the A2A agent. The agent provides a set of tools for creating and managing network intents.

### Example

Here's an example of how to create a new network intent using the A2A agent:

```bash
# (Assuming you have a client for interacting with the A2A agent)
a2a-client --agent <agent-url> create-intent --name "My New Intent" --description "A new network intent"
```
