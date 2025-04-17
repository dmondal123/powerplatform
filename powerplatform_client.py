#!/usr/bin/env python3
import asyncio
import json
import sys
import os
from typing import Dict, Any, Optional, List

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

async def display_entity_metadata(metadata: Dict[str, Any]):
    """Display formatted entity metadata."""
    # Extract and display key information
    entity_name = metadata.get("LogicalName", "Unknown")
    display_name = metadata.get("DisplayName", {}).get("UserLocalizedLabel", {}).get("Label", entity_name)
    schema_name = metadata.get("SchemaName", "Unknown")
    description = metadata.get("Description", {}).get("UserLocalizedLabel", {}).get("Label", "No description")
    primary_id = metadata.get("PrimaryIdAttribute", "Unknown")
    primary_name = metadata.get("PrimaryNameAttribute", "Unknown")
    
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
        print(json.dumps(metadata, indent=2))

async def display_entity_attributes(attributes: Dict[str, Any], entity_name: str):
    """Display formatted entity attributes."""
    if "value" not in attributes or not attributes["value"]:
        print(f"No attributes found for entity '{entity_name}'")
        return
    
    print(f"\n=== Attributes for {entity_name} ===")
    print(f"Total attributes: {len(attributes['value'])}")
    
    # Display first 10 attributes
    print("\nFirst 10 attributes:")
    for i, attr in enumerate(attributes["value"][:10]):
        print(f"{i+1}. {attr.get('LogicalName')}")
    
    # Ask if user wants to see all attributes
    see_all = input("\nDo you want to see all attributes? (y/n): ").lower() == 'y'
    if see_all:
        print("\n=== All Attributes ===")
        for i, attr in enumerate(attributes["value"]):
            print(f"{i+1}. {attr.get('LogicalName')}")

async def display_entity_relationships(relationships: Dict[str, Any], entity_name: str):
    """Display formatted entity relationships."""
    one_to_many = relationships.get("oneToMany", {}).get("value", [])
    many_to_many = relationships.get("manyToMany", {}).get("value", [])
    
    print(f"\n=== Relationships for {entity_name} ===")
    print(f"One-to-Many relationships: {len(one_to_many)}")
    print(f"Many-to-Many relationships: {len(many_to_many)}")
    
    # Display one-to-many relationships
    if one_to_many:
        print("\nOne-to-Many relationships:")
        for i, rel in enumerate(one_to_many[:5]):  # Show first 5
            print(f"{i+1}. {rel.get('SchemaName')}: {entity_name} → {rel.get('ReferencingEntity')}")
    
    # Display many-to-many relationships
    if many_to_many:
        print("\nMany-to-Many relationships:")
        for i, rel in enumerate(many_to_many[:5]):  # Show first 5
            related_entity = rel.get('Entity1LogicalName') if rel.get('Entity1LogicalName') != entity_name else rel.get('Entity2LogicalName')
            print(f"{i+1}. {rel.get('SchemaName')}: {entity_name} ↔ {related_entity}")

async def main():
    """Main function to demonstrate using the PowerPlatform MCP client."""
    # Check if entity name was provided as command line argument
    if len(sys.argv) < 2:
        print("Usage: python powerplatform_client.py <entity_name>")
        print("Example: python powerplatform_client.py account")
        sys.exit(1)
    
    entity_name = sys.argv[1]
    
    # Create server parameters for stdio connection
    server_params = StdioServerParameters(
        command="python",  # Executable
        args=["powerplatform_mcp_server.py"],  # Server script
        env={
            # Pass through environment variables
            "POWERPLATFORM_URL": os.environ.get("POWERPLATFORM_URL", ""),
            "POWERPLATFORM_CLIENT_ID": os.environ.get("POWERPLATFORM_CLIENT_ID", ""),
            "POWERPLATFORM_CLIENT_SECRET": os.environ.get("POWERPLATFORM_CLIENT_SECRET", ""),
            "POWERPLATFORM_TENANT_ID": os.environ.get("POWERPLATFORM_TENANT_ID", "")
        }
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                
                print("Connected to PowerPlatform MCP server")
                
                # List available tools
                print("\nAvailable tools:")
                tools = await session.list_tools()
                for tool in tools:
                    print(f"- {tool.name}: {tool.description}")
                
                # List available prompts
                print("\nAvailable prompts:")
                prompts = await session.list_prompts()
                for prompt in prompts:
                    print(f"- {prompt.name}: {prompt.description}")
                
                while True:
                    print("\n=== PowerPlatform MCP Client ===")
                    print("1. Get entity metadata")
                    print("2. Get entity attributes")
                    print("3. Get entity relationships")
                    print("4. Use entity overview prompt")
                    print("5. Query records")
                    print("6. Exit")
                    
                    choice = input("\nEnter your choice (1-6): ")
                    
                    if choice == "1":
                        print(f"\nGetting metadata for entity: {entity_name}")
                        result = await session.call_tool("get-entity-metadata", {"entityName": entity_name})
                        
                        # Extract JSON from the text content
                        text = result.content[0].text
                        json_start = text.find('{\n')
                        if json_start >= 0:
                            json_str = text[json_start:]
                            metadata = json.loads(json_str)
                            await display_entity_metadata(metadata)
                        else:
                            print("Failed to parse metadata response")
                    
                    elif choice == "2":
                        print(f"\nGetting attributes for entity: {entity_name}")
                        result = await session.call_tool("get-entity-attributes", {"entityName": entity_name})
                        
                        # Extract JSON from the text content
                        text = result.content[0].text
                        json_start = text.find('{\n')
                        if json_start >= 0:
                            json_str = text[json_start:]
                            attributes = json.loads(json_str)
                            await display_entity_attributes(attributes, entity_name)
                        else:
                            print("Failed to parse attributes response")
                    
                    elif choice == "3":
                        print(f"\nGetting relationships for entity: {entity_name}")
                        result = await session.call_tool("get-entity-relationships", {"entityName": entity_name})
                        
                        # Extract JSON from the text content
                        text = result.content[0].text
                        json_start = text.find('{\n')
                        if json_start >= 0:
                            json_str = text[json_start:]
                            relationships = json.loads(json_str)
                            await display_entity_relationships(relationships, entity_name)
                        else:
                            print("Failed to parse relationships response")
                    
                    elif choice == "4":
                        print(f"\nGetting entity overview prompt for: {entity_name}")
                        prompt_result = await session.get_prompt("entity-overview", {"entityName": entity_name})
                        
                        # Display the prompt content
                        if prompt_result and prompt_result.messages:
                            for message in prompt_result.messages:
                                if hasattr(message.content, 'text'):
                                    print("\n" + message.content.text)
                                else:
                                    print("\n" + str(message.content))
                        else:
                            print("No prompt content returned")
                    
                    elif choice == "5":
                        entity_plural = input("Enter entity plural name (e.g., accounts): ")
                        filter_expr = input("Enter filter expression (e.g., name ne null): ")
                        max_records = input("Enter max records (default 10): ") or "10"
                        
                        print(f"\nQuerying {entity_plural} with filter: {filter_expr}")
                        result = await session.call_tool("query-records", {
                            "entityNamePlural": entity_plural,
                            "filter": filter_expr,
                            "maxRecords": int(max_records)
                        })
                        
                        # Extract JSON from the text content
                        text = result.content[0].text
                        json_start = text.find('{\n')
                        if json_start >= 0:
                            json_str = text[json_start:]
                            records = json.loads(json_str)
                            
                            if "value" in records and records["value"]:
                                print(f"\nFound {len(records['value'])} records:")
                                for i, record in enumerate(records["value"]):
                                    print(f"\nRecord {i+1}:")
                                    print(json.dumps(record, indent=2))
                            else:
                                print("No records found matching the criteria")
                        else:
                            print("Failed to parse query response")
                    
                    elif choice == "6":
                        print("Exiting...")
                        break
                    
                    else:
                        print("Invalid choice. Please enter a number between 1 and 6.")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 