"""
MCP-over-HTTP Bridge for ServiceNow MCP Server
This creates a proper HTTP bridge for the MCP protocol.
"""

from flask import Flask, request, jsonify
import asyncio
import json
import os
import logging
from typing import Dict, Any
import sys

# Add the mcp_server_servicenow to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("MCP library not available, using fallback mode")

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MCPBridge:
    """Bridge between HTTP requests and MCP server."""
    
    def __init__(self):
        self.instance_url = os.getenv('SERVICENOW_INSTANCE_URL')
        self.username = os.getenv('SERVICENOW_USERNAME')
        self.password = os.getenv('SERVICENOW_PASSWORD')
        
        if not all([self.instance_url, self.username, self.password]):
            raise ValueError("Missing ServiceNow credentials in environment variables")
    
    async def call_mcp_server(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call the MCP server with given method and parameters."""
        
        # Create server parameters
        server_params = StdioServerParameters(
            command="python",
            args=[
                "-m", "mcp_server_servicenow.cli",
                "--url", self.instance_url,
                "--username", self.username,
                "--password", self.password
            ],
            env={
                **os.environ,
                "SERVICENOW_INSTANCE_URL": self.instance_url,
                "SERVICENOW_USERNAME": self.username,
                "SERVICENOW_PASSWORD": self.password
            }
        )
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()
                    
                    if method == "list_resources":
                        resources = await session.list_resources()
                        return {
                            "resources": [
                                {
                                    "uri": r.uri,
                                    "name": r.name,
                                    "description": r.description
                                }
                                for r in resources.resources
                            ]
                        }
                    
                    elif method == "list_tools":
                        tools = await session.list_tools()
                        return {
                            "tools": [
                                {
                                    "name": t.name,
                                    "description": t.description,
                                    "inputSchema": t.inputSchema
                                }
                                for t in tools.tools
                            ]
                        }
                    
                    elif method == "call_tool":
                        tool_name = params.get("name")
                        tool_params = params.get("arguments", {})
                        
                        result = await session.call_tool(tool_name, tool_params)
                        return {
                            "result": result.content
                        }
                    
                    elif method == "read_resource":
                        resource_uri = params.get("uri")
                        result = await session.read_resource(resource_uri)
                        return {
                            "contents": result.contents
                        }
                    
                    else:
                        raise ValueError(f"Unknown method: {method}")
        
        except Exception as e:
            logger.error(f"Error calling MCP server: {str(e)}")
            raise


# Global bridge instance
mcp_bridge = None


def get_bridge():
    """Get or create MCP bridge instance."""
    global mcp_bridge
    if mcp_bridge is None:
        mcp_bridge = MCPBridge()
    return mcp_bridge


@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "ServiceNow MCP-over-HTTP Bridge",
        "version": "1.0.0",
        "mcp_available": MCP_AVAILABLE,
        "endpoints": {
            "health": "GET /",
            "mcp": "POST /mcp",
            "list_resources": "GET /mcp/resources",
            "list_tools": "GET /mcp/tools",
            "call_tool": "POST /mcp/tool/<tool_name>",
            "read_resource": "GET /mcp/resource?uri=<uri>"
        }
    }), 200


@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    """
    Generic MCP endpoint.
    
    Expected JSON:
    {
        "method": "list_resources" | "list_tools" | "call_tool" | "read_resource",
        "params": {}
    }
    """
    try:
        if not MCP_AVAILABLE:
            return jsonify({
                "error": "MCP library not available",
                "hint": "Install with: pip install mcp"
            }), 500
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        method = data.get('method')
        params = data.get('params', {})
        
        if not method:
            return jsonify({"error": "Method is required"}), 400
        
        logger.info(f"MCP request: {method} with params: {params}")
        
        # Run async function in sync context
        bridge = get_bridge()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(bridge.call_mcp_server(method, params))
            return jsonify(result), 200
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in MCP endpoint: {str(e)}")
        return jsonify({
            "error": str(e),
            "type": type(e).__name__
        }), 500


@app.route('/mcp/resources', methods=['GET'])
def list_resources():
    """List available MCP resources."""
    try:
        if not MCP_AVAILABLE:
            return jsonify({
                "error": "MCP library not available"
            }), 500
        
        bridge = get_bridge()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                bridge.call_mcp_server("list_resources", {})
            )
            return jsonify(result), 200
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error listing resources: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/mcp/tools', methods=['GET'])
def list_tools():
    """List available MCP tools."""
    try:
        if not MCP_AVAILABLE:
            return jsonify({
                "error": "MCP library not available"
            }), 500
        
        bridge = get_bridge()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                bridge.call_mcp_server("list_tools", {})
            )
            return jsonify(result), 200
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error listing tools: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/mcp/tool/<tool_name>', methods=['POST'])
def call_tool(tool_name: str):
    """
    Call an MCP tool.
    
    Expected JSON body contains the tool arguments.
    """
    try:
        if not MCP_AVAILABLE:
            return jsonify({
                "error": "MCP library not available"
            }), 500
        
        arguments = request.get_json() or {}
        
        bridge = get_bridge()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                bridge.call_mcp_server("call_tool", {
                    "name": tool_name,
                    "arguments": arguments
                })
            )
            return jsonify(result), 200
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error calling tool: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/mcp/resource', methods=['GET'])
def read_resource():
    """
    Read an MCP resource.
    
    Query parameter: uri (e.g., servicenow://incidents)
    """
    try:
        if not MCP_AVAILABLE:
            return jsonify({
                "error": "MCP library not available"
            }), 500
        
        uri = request.args.get('uri')
        if not uri:
            return jsonify({"error": "uri parameter is required"}), 400
        
        bridge = get_bridge()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                bridge.call_mcp_server("read_resource", {"uri": uri})
            )
            return jsonify(result), 200
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error reading resource: {str(e)}")
        return jsonify({"error": str(e)}), 500


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


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting ServiceNow MCP-over-HTTP Bridge on port {port}")
    logger.info(f"MCP library available: {MCP_AVAILABLE}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )