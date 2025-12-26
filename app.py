"""
Flask wrapper for ServiceNow MCP Server to enable remote HTTP access.
This creates an HTTP endpoint that communicates with the MCP server.

This version directly interacts with ServiceNow API without requiring
the MCP server's internal create_server function.
"""

from flask import Flask, request, jsonify
import os
import requests
from requests.auth import HTTPBasicAuth
import logging
import json
from typing import Dict, Any, Optional

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ServiceNowClient:
    """Direct ServiceNow API client."""
    
    def __init__(self, instance_url: str, username: str, password: str):
        """Initialize ServiceNow client."""
        self.instance_url = instance_url.rstrip('/')
        self.username = username
        self.password = password
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        logger.info(f"ServiceNow client initialized for: {self.instance_url}")
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make a request to ServiceNow API."""
        url = f"{self.instance_url}/api/now/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, auth=self.auth, headers=self.headers, params=data)
            elif method.upper() == 'POST':
                response = requests.post(url, auth=self.auth, headers=self.headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, auth=self.auth, headers=self.headers, json=data)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, auth=self.auth, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"ServiceNow API error: {str(e)}")
            raise
    
    def create_incident(self, short_description: str, **kwargs) -> Dict:
        """Create a new incident."""
        data = {
            'short_description': short_description,
            **kwargs
        }
        return self._make_request('POST', 'table/incident', data)
    
    def get_incident(self, sys_id: str) -> Dict:
        """Get an incident by sys_id."""
        return self._make_request('GET', f'table/incident/{sys_id}')
    
    def update_incident(self, sys_id: str, **kwargs) -> Dict:
        """Update an incident."""
        return self._make_request('PATCH', f'table/incident/{sys_id}', kwargs)
    
    def search_incidents(self, query: str, limit: int = 10) -> Dict:
        """Search incidents."""
        params = {
            'sysparm_query': query,
            'sysparm_limit': limit
        }
        return self._make_request('GET', 'table/incident', params)
    
    def get_table_records(self, table: str, query: Optional[str] = None, limit: int = 10) -> Dict:
        """Get records from any table."""
        params = {'sysparm_limit': limit}
        if query:
            params['sysparm_query'] = query
        return self._make_request('GET', f'table/{table}', params)
    
    def get_record(self, table: str, sys_id: str) -> Dict:
        """Get a specific record by sys_id."""
        return self._make_request('GET', f'table/{table}/{sys_id}')


# Initialize ServiceNow client
snow_client: Optional[ServiceNowClient] = None


def get_snow_client() -> ServiceNowClient:
    """Get or create ServiceNow client."""
    global snow_client
    
    if snow_client is None:
        instance_url = os.getenv('SERVICENOW_INSTANCE_URL')
        username = os.getenv('SERVICENOW_USERNAME')
        password = os.getenv('SERVICENOW_PASSWORD')
        
        if not all([instance_url, username, password]):
            raise ValueError(
                "Missing required environment variables: "
                "SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, SERVICENOW_PASSWORD"
            )
        
        snow_client = ServiceNowClient(instance_url, username, password)
    
    return snow_client


@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "ServiceNow MCP Server (HTTP Wrapper)",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /",
            "tools": "GET /mcp/tools",
            "resources": "GET /mcp/resources",
            "create_incident": "POST /mcp/incident/create",
            "get_incident": "GET /mcp/incident/<sys_id>",
            "update_incident": "PATCH /mcp/incident/<sys_id>",
            "search_incidents": "GET /mcp/incidents/search?query=<query>",
            "query_table": "GET /mcp/table/<table_name>"
        }
    }), 200


@app.route('/mcp/tools', methods=['GET'])
def list_tools():
    """List all available MCP tools."""
    tools = [
        {
            "name": "create_incident",
            "description": "Create a new incident in ServiceNow",
            "endpoint": "POST /mcp/incident/create"
        },
        {
            "name": "update_incident",
            "description": "Update an existing incident",
            "endpoint": "PATCH /mcp/incident/<sys_id>"
        },
        {
            "name": "get_incident",
            "description": "Get a specific incident by sys_id",
            "endpoint": "GET /mcp/incident/<sys_id>"
        },
        {
            "name": "search_incidents",
            "description": "Search for incidents",
            "endpoint": "GET /mcp/incidents/search?query=<query>"
        },
        {
            "name": "query_table",
            "description": "Query any ServiceNow table",
            "endpoint": "GET /mcp/table/<table_name>"
        }
    ]
    
    return jsonify({"tools": tools}), 200


@app.route('/mcp/resources', methods=['GET'])
def list_resources():
    """List all available MCP resources."""
    resources = [
        {
            "uri": "servicenow://incidents",
            "description": "List recent incidents",
            "endpoint": "GET /mcp/incidents"
        },
        {
            "uri": "servicenow://incidents/{sys_id}",
            "description": "Get a specific incident",
            "endpoint": "GET /mcp/incident/<sys_id>"
        },
        {
            "uri": "servicenow://tables/{table}",
            "description": "Get records from a specific table",
            "endpoint": "GET /mcp/table/<table_name>"
        }
    ]
    
    return jsonify({"resources": resources}), 200


@app.route('/mcp/incident/create', methods=['POST'])
def create_incident():
    """
    Create a new incident.
    
    Expected JSON body:
    {
        "short_description": "Issue description",
        "description": "Detailed description",
        "priority": "3",
        "urgency": "3",
        "category": "inquiry"
    }
    """
    try:
        client = get_snow_client()
        data = request.get_json()
        
        if not data or not data.get('short_description'):
            return jsonify({
                "error": "short_description is required"
            }), 400
        
        logger.info(f"Creating incident: {data.get('short_description')}")
        
        result = client.create_incident(**data)
        
        return jsonify({
            "status": "success",
            "message": "Incident created successfully",
            "result": result
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating incident: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/mcp/incident/<sys_id>', methods=['GET'])
def get_incident(sys_id: str):
    """Get a specific incident by sys_id."""
    try:
        client = get_snow_client()
        logger.info(f"Getting incident: {sys_id}")
        
        result = client.get_incident(sys_id)
        
        return jsonify({
            "status": "success",
            "result": result
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting incident: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/mcp/incident/<sys_id>', methods=['PATCH', 'PUT'])
def update_incident(sys_id: str):
    """
    Update an existing incident.
    
    Expected JSON body:
    {
        "state": "2",
        "work_notes": "Working on this issue"
    }
    """
    try:
        client = get_snow_client()
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "No update data provided"
            }), 400
        
        logger.info(f"Updating incident: {sys_id}")
        
        result = client.update_incident(sys_id, **data)
        
        return jsonify({
            "status": "success",
            "message": "Incident updated successfully",
            "result": result
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating incident: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/mcp/incidents/search', methods=['GET'])
def search_incidents():
    """
    Search for incidents.
    
    Query parameters:
    - query: ServiceNow query string (e.g., "short_descriptionLIKEemail")
    - limit: Maximum number of results (default: 10)
    """
    try:
        client = get_snow_client()
        query = request.args.get('query', '')
        limit = int(request.args.get('limit', 10))
        
        if not query:
            return jsonify({
                "error": "query parameter is required"
            }), 400
        
        logger.info(f"Searching incidents with query: {query}")
        
        result = client.search_incidents(query, limit)
        
        return jsonify({
            "status": "success",
            "result": result
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching incidents: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/mcp/incidents', methods=['GET'])
def list_incidents():
    """List recent incidents."""
    try:
        client = get_snow_client()
        limit = int(request.args.get('limit', 10))
        
        logger.info(f"Listing {limit} recent incidents")
        
        result = client.get_table_records('incident', limit=limit)
        
        return jsonify({
            "status": "success",
            "result": result
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing incidents: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/mcp/table/<table_name>', methods=['GET'])
def query_table(table_name: str):
    """
    Query any ServiceNow table.
    
    Query parameters:
    - query: ServiceNow query string
    - limit: Maximum number of results (default: 10)
    """
    try:
        client = get_snow_client()
        query = request.args.get('query')
        limit = int(request.args.get('limit', 10))
        
        logger.info(f"Querying table: {table_name}")
        
        result = client.get_table_records(table_name, query, limit)
        
        return jsonify({
            "status": "success",
            "table": table_name,
            "result": result
        }), 200
        
    except Exception as e:
        logger.error(f"Error querying table: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/mcp/table/<table_name>/<sys_id>', methods=['GET'])
def get_record(table_name: str, sys_id: str):
    """Get a specific record from any table."""
    try:
        client = get_snow_client()
        logger.info(f"Getting record from {table_name}: {sys_id}")
        
        result = client.get_record(table_name, sys_id)
        
        return jsonify({
            "status": "success",
            "table": table_name,
            "result": result
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting record: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        "error": "Endpoint not found",
        "message": "Please check the API documentation at GET /"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        "error": "Internal server error",
        "message": str(error)
    }), 500


# Test connection on startup
try:
    test_client = get_snow_client()
    logger.info("✓ ServiceNow client initialized successfully")
except Exception as e:
    logger.error(f"✗ Failed to initialize ServiceNow client: {str(e)}")
    logger.error("The server will start but API calls will fail until credentials are configured")


if __name__ == '__main__':
    # For local development
    port = int(os.getenv('PORT', 8000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting ServiceNow MCP HTTP Wrapper on port {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )