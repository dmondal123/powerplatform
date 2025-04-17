#!/usr/bin/env python3
import asyncio
import sys

# Import the main function from our server module
from powerplatform_mcp_server import main

def main_entry():
    """
    Entry point for the PowerPlatform MCP server.
    This function is called when the package is run as a script.
    """
    try:
        # Run the async main function
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main_entry() 