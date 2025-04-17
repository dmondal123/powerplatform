#!/usr/bin/env python3
import os
import json
import asyncio
import sys
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from powerplatform_service import PowerPlatformService, PowerPlatformConfig

# Environment configuration
POWERPLATFORM_CONFIG = PowerPlatformConfig(
    organization_url=os.environ.get("POWERPLATFORM_URL", ""),
    client_id=os.environ.get("POWERPLATFORM_CLIENT_ID", ""),
    client_secret=os.environ.get("POWERPLATFORM_CLIENT_SECRET", ""),
    tenant_id=os.environ.get("POWERPLATFORM_TENANT_ID", "")
)

# Global service instance
powerplatform_service = None

# Function to initialize PowerPlatformService on demand
async def get_powerplatform_service():
    global powerplatform_service
    if not powerplatform_service:
        # Check if configuration is complete
        missing_config = []
        if not POWERPLATFORM_CONFIG.organization_url:
            missing_config.append("organization_url")
        if not POWERPLATFORM_CONFIG.client_id:
            missing_config.append("client_id")
        if not POWERPLATFORM_CONFIG.client_secret:
            missing_config.append("client_secret")
        if not POWERPLATFORM_CONFIG.tenant_id:
            missing_config.append("tenant_id")
        
        if missing_config:
            raise Exception(f"Missing PowerPlatform configuration: {', '.join(missing_config)}. Set these in environment variables.")
        
        # Initialize service
        powerplatform_service = PowerPlatformService(POWERPLATFORM_CONFIG)
        print("PowerPlatform service initialized", file=sys.stderr)
    
    return powerplatform_service

# Create server instance
server = Server("powerplatform-mcp")

# Define prompt types
PROMPT_TYPES = [
    "ENTITY_OVERVIEW",
    "ATTRIBUTE_DETAILS",
    "QUERY_TEMPLATE",
    "RELATIONSHIP_MAP"
]

# Pre-defined PowerPlatform Prompts
class PowerPlatformPrompts:
    @staticmethod
    def entity_overview(entity_name):
        return (
            f"## Power Platform Entity: {entity_name}\n\n"
            f"This is an overview of the '{entity_name}' entity in Microsoft Power Platform/Dataverse:\n\n"
            f"### Entity Details\n{{entity_details}}\n\n"
            f"### Attributes\n{{key_attributes}}\n\n"
            f"### Relationships\n{{relationships}}\n\n"
            f"You can query this entity using OData filters against the plural name."
        )
    
    @staticmethod
    def attribute_details(entity_name, attribute_name):
        return (
            f"## Attribute: {attribute_name}\n\n"
            f"Details for the '{attribute_name}' attribute of the '{entity_name}' entity:\n\n"
            f"{{attribute_details}}\n\n"
            f"### Usage Notes\n"
            f"- Data Type: {{data_type}}\n"
            f"- Required: {{required}}\n"
            f"- Max Length: {{max_length}}"
        )
    
    @staticmethod
    def query_template(entity_name_plural):
        return (
            f"## OData Query Template for {entity_name_plural}\n\n"
            f"Use this template to build queries against the {entity_name_plural} entity:\n\n"
            f"```\n{entity_name_plural}?$select={{selected_fields}}&$filter={{filter_conditions}}&$orderby={{order_by}}&$top={{max_records}}\n```\n\n"
            f"### Common Filter Examples\n"
            f"- Equals: `name eq 'Contoso'`\n"
            f"- Contains: `contains(name, 'Contoso')`\n"
            f"- Greater than date: `createdon gt 2023-01-01T00:00:00Z`\n"
            f"- Multiple conditions: `name eq 'Contoso' and statecode eq 0`"
        )
    
    @staticmethod
    def relationship_map(entity_name):
        return (
            f"## Relationship Map for {entity_name}\n\n"
            f"This shows all relationships for the '{entity_name}' entity:\n\n"
            f"### One-to-Many Relationships ({entity_name} as Primary)\n{{one_to_many_primary}}\n\n"
            f"### One-to-Many Relationships ({entity_name} as Related)\n{{one_to_many_related}}\n\n"
            f"### Many-to-Many Relationships\n{{many_to_many}}\n\n"
        )

# List available tools
@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="get-entity-metadata",
            description="Get metadata about a Power Platform entity",
            arguments=[
                types.ToolArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                )
            ]
        ),
        types.Tool(
            name="get-entity-attributes",
            description="Get attributes/fields of a Power Platform entity",
            arguments=[
                types.ToolArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                )
            ]
        ),
        types.Tool(
            name="get-entity-attribute",
            description="Get a specific attribute/field of a Power Platform entity",
            arguments=[
                types.ToolArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                ),
                types.ToolArgument(
                    name="attributeName",
                    description="The logical name of the attribute",
                    required=True
                )
            ]
        ),
        types.Tool(
            name="get-entity-relationships",
            description="Get relationships for a Power Platform entity",
            arguments=[
                types.ToolArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                )
            ]
        ),
        types.Tool(
            name="get-global-option-set",
            description="Get a global option set definition",
            arguments=[
                types.ToolArgument(
                    name="optionSetName",
                    description="The name of the global option set",
                    required=True
                )
            ]
        ),
        types.Tool(
            name="get-record",
            description="Get a specific record by ID",
            arguments=[
                types.ToolArgument(
                    name="entityNamePlural",
                    description="The plural name of the entity (e.g., 'accounts', 'contacts')",
                    required=True
                ),
                types.ToolArgument(
                    name="recordId",
                    description="The ID of the record to retrieve",
                    required=True
                )
            ]
        ),
        types.Tool(
            name="query-records",
            description="Query records using an OData filter expression",
            arguments=[
                types.ToolArgument(
                    name="entityNamePlural",
                    description="The plural name of the entity (e.g., 'accounts', 'contacts')",
                    required=True
                ),
                types.ToolArgument(
                    name="filter",
                    description="OData filter expression (e.g., \"name eq 'test'\")",
                    required=True
                ),
                types.ToolArgument(
                    name="maxRecords",
                    description="Maximum number of records to retrieve (default: 50)",
                    required=False
                )
            ]
        ),
        types.Tool(
            name="use-powerplatform-prompt",
            description="Use a predefined prompt template",
            arguments=[
                types.ToolArgument(
                    name="promptType",
                    description=f"Type of prompt to use. One of: {', '.join(PROMPT_TYPES)}",
                    required=True
                ),
                types.ToolArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                ),
                types.ToolArgument(
                    name="attributeName",
                    description="The logical name of the attribute (required for ATTRIBUTE_DETAILS prompt)",
                    required=False
                )
            ]
        )
    ]

# List available prompts
@server.list_prompts()
async def handle_list_prompts() -> List[types.Prompt]:
    return [
        types.Prompt(
            name="entity-overview",
            description="Get an overview of a Power Platform entity",
            arguments=[
                types.PromptArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                )
            ]
        ),
        types.Prompt(
            name="attribute-details",
            description="Get detailed information about a specific entity attribute",
            arguments=[
                types.PromptArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                ),
                types.PromptArgument(
                    name="attributeName",
                    description="The logical name of the attribute",
                    required=True
                )
            ]
        ),
        types.Prompt(
            name="query-template",
            description="Get a template for querying a Power Platform entity",
            arguments=[
                types.PromptArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                )
            ]
        ),
        types.Prompt(
            name="relationship-map",
            description="Get a list of relationships for a Power Platform entity",
            arguments=[
                types.PromptArgument(
                    name="entityName",
                    description="The logical name of the entity",
                    required=True
                )
            ]
        )
    ]

# Handle get-entity-metadata tool
@server.call_tool()
async def handle_get_entity_metadata(name: str, arguments: Dict[str, Any]) -> types.ToolCallResult:
    if name != "get-entity-metadata":
        raise ValueError(f"Unknown tool: {name}")
    
    try:
        entity_name = arguments.get("entityName")
        if not entity_name:
            raise ValueError("entityName is required")
        
        service = await get_powerplatform_service()
        metadata = await service.get_entity_metadata(entity_name)
        
        return types.ToolCallResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"Metadata for entity '{entity_name}':\n\n{json.dumps(metadata, indent=2)}"
                )
            ]
        )
    except Exception as e:
        print(f"Error getting entity metadata: {e}", file=sys.stderr)
        return types.ToolCallResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"Failed to get entity metadata: {str(e)}"
                )
            ]
        )

# Handle get-entity-attributes tool
@server.call_tool()
async def handle_get_entity_attributes(name: str, arguments: Dict[str, Any]) -> types.ToolCallResult:
    if name != "get-entity-attributes":
        raise ValueError(f"Unknown tool: {name}")
    
    try:
        entity_name = arguments.get("entityName")
        if not entity_name:
            raise ValueError("entityName is required")
        
        service = await get_powerplatform_service()
        attributes = await service.get_entity_attributes(entity_name)
        
        return types.ToolCallResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"Attributes for entity '{entity_name}':\n\n{json.dumps(attributes, indent=2)}"
                )
            ]
        )
    except Exception as e:
        print(f"Error getting entity attributes: {e}", file=sys.stderr)
        return types.ToolCallResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"Failed to get entity attributes: {str(e)}"
                )
            ]
        )

# Handle entity-overview prompt
@server.get_prompt()
async def handle_get_prompt(name: str, arguments: Dict[str, str] | None) -> types.GetPromptResult:
    if not arguments:
        raise ValueError("Arguments are required")
    
    try:
        if name == "entity-overview":
            entity_name = arguments.get("entityName")
            if not entity_name:
                raise ValueError("entityName is required")
            
            service = await get_powerplatform_service()
            
            # Get entity metadata and key attributes
            metadata = await service.get_entity_metadata(entity_name)
            attributes = await service.get_entity_attributes(entity_name)
            
            # Format entity details
            entity_details = (
                f"- Display Name: {metadata.get('DisplayName', {}).get('UserLocalizedLabel', {}).get('Label', entity_name)}\n"
                f"- Schema Name: {metadata.get('SchemaName')}\n"
                f"- Description: {metadata.get('Description', {}).get('UserLocalizedLabel', {}).get('Label', 'No description')}\n"
                f"- Primary Key: {metadata.get('PrimaryIdAttribute')}\n"
                f"- Primary Name: {metadata.get('PrimaryNameAttribute')}"
            )
            
            # Get key attributes
            key_attributes = "\n".join([
                f"- {attr.get('LogicalName')}: {attr.get('@odata.type', 'Unknown type')}"
                for attr in attributes.get("value", [])
            ])
            
            # Get relationships summary
            relationships = await service.get_entity_relationships(entity_name)
            one_to_many_count = len(relationships.get("oneToMany", {}).get("value", []))
            many_to_many_count = len(relationships.get("manyToMany", {}).get("value", []))
            
            relationships_summary = (
                f"- One-to-Many Relationships: {one_to_many_count}\n"
                f"- Many-to-Many Relationships: {many_to_many_count}"
            )
            
            prompt_content = PowerPlatformPrompts.entity_overview(entity_name)
            replacements = {
                "{{entity_details}}": entity_details,
                "{{key_attributes}}": key_attributes,
                "{{relationships}}": relationships_summary
            }
            
            # Replace all placeholders in the template
            for placeholder, value in replacements.items():
                prompt_content = prompt_content.replace(placeholder, value)
            
            return types.GetPromptResult(
                description=f"Overview of the {entity_name} entity",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=prompt_content
                        )
                    )
                ]
            )
        
        # Add other prompt handlers here...
        
        else:
            raise ValueError(f"Unknown prompt: {name}")
    
    except Exception as e:
        print(f"Error getting prompt: {e}", file=sys.stderr)
        raise ValueError(f"Failed to get prompt: {str(e)}")

async def run():
    print("Initializing PowerPlatform MCP Server...", file=sys.stderr)
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="powerplatform-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(run()) 