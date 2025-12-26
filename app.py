from flask import Flask, request, jsonify
import subprocess
import json

app = Flask(__name__)

@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    try:
        data = request.get_json()
        # Pass request to MCP server
        result = subprocess.run(
            ['python', '-m', 'mcp_server_servicenow.cli'],
            input=json.dumps(data),
            capture_output=True,
            text=True
        )
        return jsonify(json.loads(result.stdout))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)