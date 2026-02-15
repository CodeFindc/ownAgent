import sys
import json
import logging

# Configure logging to stderr to avoid interfering with stdout
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='[Server] %(message)s')

def log(msg):
    logging.info(msg)

def main():
    log("Starting Mock MCP Server...")
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line)
            log(f"Received: {line.strip()}")
            
            response = handle_request(request)
            if response:
                response_str = json.dumps(response)
                log(f"Sending: {response_str}")
                sys.stdout.write(response_str + "\n")
                sys.stdout.flush()
                
        except json.JSONDecodeError:
            log("Invalid JSON received")
        except Exception as e:
            log(f"Error: {e}")

def handle_request(request):
    method = request.get("method")
    req_id = request.get("id")
    
    # Handle Initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {
                    "name": "mock-server",
                    "version": "1.0.0"
                }
            }
        }
    
    # Handle Notifications (no response needed)
    if method == "notifications/initialized":
        return None
    
    # Handle Tools List
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "mock_echo",
                        "description": "Echo back the input",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"}
                            },
                            "required": ["message"]
                        }
                    },
                     {
                        "name": "mock_add",
                        "description": "Add two numbers",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "a": {"type": "number"},
                                "b": {"type": "number"}
                            },
                            "required": ["a", "b"]
                        }
                    }
                ]
            }
        }
        
    # Handle Tools Call
    if method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        
        content = []
        is_error = False
        
        if name == "mock_echo":
            content = [{"type": "text", "text": f"Echo: {args.get('message')}"}]
        elif name == "mock_add":
            try:
                a = args.get("a")
                b = args.get("b")
                result = a + b
                content = [{"type": "text", "text": str(result)}]
            except Exception:
                content = [{"type": "text", "text": "Invalid arguments"}]
                is_error = True
        else:
            content = [{"type": "text", "text": f"Unknown tool: {name}"}]
            is_error = True
            
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": content,
                "isError": is_error
            }
        }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "Method not found"}
    }

if __name__ == "__main__":
    main()
