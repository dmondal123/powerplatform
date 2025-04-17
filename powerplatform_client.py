#!/usr/bin/env python3
import json
import sys
import uuid
import subprocess
import time
from typing import Dict, Any, Optional

class PowerPlatformClient:
    """
    A client for communicating with the PowerPlatform MCP server.
    """
    def __init__(self, server_command=["powerplatform-mcp"]):
        """
        Initialize the client with the command to start the server.
        
        Args:
            server_command: List containing the command and arguments to start the server
        """
        self.server_process = None
        self.server_command = server_command
        
    def start_server(self):
        """Start the PowerPlatform MCP server as a subprocess."""
        if self.server_process is None or self.server_process.poll() is not None:
            # Start the server process
            self.server_process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            # Give the server a moment to initialize
            time.sleep(1)
            
    def stop_server(self):
        """Stop the server process if it's running."""
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            self.server_process = None
            
    def invoke(self, function_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Invoke a function on the PowerPlatform MCP server.
        
        Args:
            function_name: The name of the function to invoke
            params: The parameters to pass to the function
            
        Returns:
            The result of the function call, or None if an error occurred
        """
        if not self.server_process or self.server_process.poll() is not None:
            self.start_server()
            
        # Create a request with a unique ID
        request = {
            "id": str(uuid.uuid4()),
            "function": function_name,
            "params": params
        }
        
        # Send the request to the server
        request_json = json.dumps(request) + "\n"
        self.server_process.stdin.write(request_json)
        self.server_process.stdin.flush()
        
        # Read the response
        response_line = self.server_process.stdout.readline()
        if not response_line:
            print("Error: No response from server", file=sys.stderr)
            return None
            
        try:
            response = json.loads(response_line)
            if "error" in response:
                print(f"Server error: {response['error']}", file=sys.stderr)
                return None
            return response.get("result")
        except json.JSONDecodeError:
            print(f"Error decoding response: {response_line}", file=sys.stderr)
            return None
            
    def __enter__(self):
        """Context manager entry."""
        self.start_server()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_server()


def main():
    """
    Main function to demonstrate using the PowerPlatform client.
    """
    # Check if entity name was provided as command line argument
    if len(sys.argv) < 2:
        print("Usage: python powerplatform_client.py <entity_name>")
        print("Example: python powerplatform_client.py account")
        sys.exit(1)
        
    entity_name = sys.argv[1]
    
    # Use the client as a context manager
    with PowerPlatformClient() as client:
        print(f"Getting metadata for entity: {entity_name}")
        
        # Invoke the get-entity-metadata function
        result = client.invoke("get-entity-metadata", {"entityName": entity_name})
        
        if result:
            # Extract and display key information
            display_name = result.get("DisplayName", {}).get("UserLocalizedLabel", {}).get("Label", entity_name)
            schema_name = result.get("SchemaName", "Unknown")
            description = result.get("Description", {}).get("UserLocalizedLabel", {}).get("Label", "No description")
            primary_id = result.get("PrimaryIdAttribute", "Unknown")
            primary_name = result.get("PrimaryNameAttribute", "Unknown")
            
            print("\n=== Entity Metadata ===")
            print(f"Display Name: {display_name}")
            print(f"Schema Name: {schema_name}")
            print(f"Description: {description}")
            print(f"Primary ID Attribute: {primary_id}")
            print(f"Primary Name Attribute: {primary_name}")
            
            # Ask if user wants to see full metadata
            see_full = input("\nDo you want to see the full metadata? (y/n): ").lower() == 'y'
            if see_full:
                print("\n=== Full Metadata ===")
                print(json.dumps(result, indent=2))
        else:
            print("Failed to get entity metadata.")


if __name__ == "__main__":
    main() 