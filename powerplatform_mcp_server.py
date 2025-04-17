#!/usr/bin/env python3
import os
import json
import asyncio
import sys
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum

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

# MCP Message models
class Content(BaseModel):
    type: str
    text: str

class Message(BaseModel):
    role: str
    content: Content

class PromptResponse(BaseModel):
    messages: List[Message]

class ToolResponse(BaseModel):
    content: List[Content]

# Prompt type enum
class PromptType(str, Enum):
    ENTITY_OVERVIEW = "ENTITY_OVERVIEW"
    ATTRIBUTE_DETAILS = "ATTRIBUTE_DETAILS"
    QUERY_TEMPLATE = "QUERY_TEMPLATE"
    RELATIONSHIP_MAP = "RELATIONSHIP_MAP"

# Request models
class EntityRequest(BaseModel):
    entityName: str

class AttributeRequest(BaseModel):
    entityName: str
    attributeName: str

class OptionSetRequest(BaseModel):
    optionSetName: str

class RecordRequest(BaseModel):
    entityNamePlural: str
    recordId: str

class QueryRequest(BaseModel):
    entityNamePlural: str
    filter: str
    maxRecords: Optional[int] = 50

class PromptRequest(BaseModel):
    promptType: PromptType
    entityName: str
    attributeName: Optional[str] = None

# MCP Server class
class McpServer:
    def __init__(self):
        self.handlers = {}
    
    def register_handler(self, function_name, handler):
        self.handlers[function_name] = handler
    
    async def handle_request(self, request_data):
        try:
            request = json.loads(request_data)
            function_name = request.get("function")
            params = request.get("params", {})
            
            if function_name not in self.handlers:
                return {"error": f"Unknown function: {function_name}"}
            
            result = await self.handlers[function_name](params)
            return {"id": request.get("id"), "result": result}
        except Exception as e:
            return {"error": str(e)}
    
    async def start(self):
        while True:
            try:
                request_data = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not request_data:
                    break
                
                response = await self.handle_request(request_data)
                print(json.dumps(response), flush=True)
            except Exception as e:
                print(json.dumps({"error": f"Server error: {str(e)}"}), flush=True)

# Handler implementations
async def handle_get_entity_metadata(params):
    try:
        request = EntityRequest(**params)
        service = await get_powerplatform_service()
        metadata = await service.get_entity_metadata(request.entityName)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Entity metadata for '{request.entityName}':\n\n{json.dumps(metadata, indent=2)}"
                }
            ]
        }
    except Exception as e:
        print(f"Error getting entity metadata: {e}", file=sys.stderr)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to get entity metadata: {str(e)}"
                }
            ]
        }

async def handle_get_entity_attributes(params):
    try:
        request = EntityRequest(**params)
        service = await get_powerplatform_service()
        attributes = await service.get_entity_attributes(request.entityName)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Attributes for entity '{request.entityName}':\n\n{json.dumps(attributes, indent=2)}"
                }
            ]
        }
    except Exception as e:
        print(f"Error getting entity attributes: {e}", file=sys.stderr)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to get entity attributes: {str(e)}"
                }
            ]
        }

async def handle_get_entity_attribute(params):
    try:
        request = AttributeRequest(**params)
        service = await get_powerplatform_service()
        attribute = await service.get_entity_attribute(request.entityName, request.attributeName)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Attribute '{request.attributeName}' for entity '{request.entityName}':\n\n{json.dumps(attribute, indent=2)}"
                }
            ]
        }
    except Exception as e:
        print(f"Error getting entity attribute: {e}", file=sys.stderr)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to get entity attribute: {str(e)}"
                }
            ]
        }

async def handle_get_entity_relationships(params):
    try:
        request = EntityRequest(**params)
        service = await get_powerplatform_service()
        relationships = await service.get_entity_relationships(request.entityName)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Relationships for entity '{request.entityName}':\n\n{json.dumps(relationships, indent=2)}"
                }
            ]
        }
    except Exception as e:
        print(f"Error getting entity relationships: {e}", file=sys.stderr)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to get entity relationships: {str(e)}"
                }
            ]
        }

async def handle_get_global_option_set(params):
    try:
        request = OptionSetRequest(**params)
        service = await get_powerplatform_service()
        option_set = await service.get_global_option_set(request.optionSetName)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Global option set '{request.optionSetName}':\n\n{json.dumps(option_set, indent=2)}"
                }
            ]
        }
    except Exception as e:
        print(f"Error getting global option set: {e}", file=sys.stderr)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to get global option set: {str(e)}"
                }
            ]
        }

async def handle_get_record(params):
    try:
        request = RecordRequest(**params)
        service = await get_powerplatform_service()
        record = await service.get_record(request.entityNamePlural, request.recordId)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Record from '{request.entityNamePlural}' with ID '{request.recordId}':\n\n{json.dumps(record, indent=2)}"
                }
            ]
        }
    except Exception as e:
        print(f"Error getting record: {e}", file=sys.stderr)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to get record: {str(e)}"
                }
            ]
        }

async def handle_query_records(params):
    try:
        request = QueryRequest(**params)
        service = await get_powerplatform_service()
        records = await service.query_records(request.entityNamePlural, request.filter, request.maxRecords)
        
        record_count = len(records.get("value", []))
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Retrieved {record_count} records from '{request.entityNamePlural}' with filter '{request.filter}':\n\n{json.dumps(records, indent=2)}"
                }
            ]
        }
    except Exception as e:
        print(f"Error querying records: {e}", file=sys.stderr)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to query records: {str(e)}"
                }
            ]
        }

async def handle_use_powerplatform_prompt(params):
    try:
        request = PromptRequest(**params)
        service = await get_powerplatform_service()
        
        prompt_content = ""
        replacements = {}
        
        if request.promptType == PromptType.ENTITY_OVERVIEW:
            # Get entity metadata and key attributes
            metadata = await service.get_entity_metadata(request.entityName)
            attributes = await service.get_entity_attributes(request.entityName)
            
            # Format entity details
            entity_details = (
                f"- Display Name: {metadata.get('DisplayName', {}).get('UserLocalizedLabel', {}).get('Label', request.entityName)}\n"
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
            relationships = await service.get_entity_relationships(request.entityName)
            one_to_many_count = len(relationships.get("oneToMany", {}).get("value", []))
            many_to_many_count = len(relationships.get("manyToMany", {}).get("value", []))
            
            relationships_summary = (
                f"- One-to-Many Relationships: {one_to_many_count}\n"
                f"- Many-to-Many Relationships: {many_to_many_count}"
            )
            
            prompt_content = PowerPlatformPrompts.entity_overview(request.entityName)
            replacements = {
                "{{entity_details}}": entity_details,
                "{{key_attributes}}": key_attributes,
                "{{relationships}}": relationships_summary
            }
            
        elif request.promptType == PromptType.ATTRIBUTE_DETAILS:
            if not request.attributeName:
                raise Exception("attributeName is required for ATTRIBUTE_DETAILS prompt")
            
            # Get attribute details
            attribute = await service.get_entity_attribute(request.entityName, request.attributeName)
            
            # Format attribute details
            attr_details = (
                f"- Display Name: {attribute.get('DisplayName', {}).get('UserLocalizedLabel', {}).get('Label', request.attributeName)}\n"
                f"- Description: {attribute.get('Description', {}).get('UserLocalizedLabel', {}).get('Label', 'No description')}\n"
                f"- Type: {attribute.get('AttributeType')}\n"
                f"- Format: {attribute.get('Format', 'N/A')}\n"
                f"- Is Required: {attribute.get('RequiredLevel', {}).get('Value', 'No')}\n"
                f"- Is Searchable: {attribute.get('IsValidForAdvancedFind', False)}"
            )
            
            prompt_content = PowerPlatformPrompts.attribute_details(request.entityName, request.attributeName)
            replacements = {
                "{{attribute_details}}": attr_details,
                "{{data_type}}": attribute.get('AttributeType', 'Unknown'),
                "{{required}}": attribute.get('RequiredLevel', {}).get('Value', 'No'),
                "{{max_length}}": str(attribute.get('MaxLength', 'N/A'))
            }
            
        elif request.promptType == PromptType.QUERY_TEMPLATE:
            # Get entity metadata to determine plural name
            metadata = await service.get_entity_metadata(request.entityName)
            entity_name_plural = metadata.get('EntitySetName')
            
            # Get a few important fields for the select example
            attributes = await service.get_entity_attributes(request.entityName)
            select_fields = ",".join([
                attr.get("LogicalName")
                for attr in attributes.get("value", [])[:5]  # Just take first 5 for example
            ])
            
            prompt_content = PowerPlatformPrompts.query_template(entity_name_plural)
            replacements = {
                "{{selected_fields}}": select_fields,
                "{{filter_conditions}}": f"{metadata.get('PrimaryNameAttribute')} eq 'Example'",
                "{{order_by}}": f"{metadata.get('PrimaryNameAttribute')} asc",
                "{{max_records}}": "50"
            }
            
        elif request.promptType == PromptType.RELATIONSHIP_MAP:
            # Get relationships
            relationships = await service.get_entity_relationships(request.entityName)
            
            # Format one-to-many relationships where this entity is primary
            one_to_many_primary = "\n".join([
                f"- {rel.get('SchemaName')}: {request.entityName} (1) → {rel.get('ReferencingEntity')} (N)"
                for rel in relationships.get("oneToMany", {}).get("value", [])
                if rel.get("ReferencingEntity") != request.entityName
            ]) or "None found"
            
            # Format one-to-many relationships where this entity is related
            one_to_many_related = "\n".join([
                f"- {rel.get('SchemaName')}: {rel.get('ReferencedEntity')} (1) → {request.entityName} (N)"
                for rel in relationships.get("oneToMany", {}).get("value", [])
                if rel.get("ReferencingEntity") == request.entityName
            ]) or "None found"
            
            # Format many-to-many relationships
            many_to_many = "\n".join([
                f"- {rel.get('SchemaName')}: {request.entityName} (N) ↔ {rel.get('Entity1LogicalName') if rel.get('Entity1LogicalName') != request.entityName else rel.get('Entity2LogicalName')} (N)"
                for rel in relationships.get("manyToMany", {}).get("value", [])
            ]) or "None found"
            
            prompt_content = PowerPlatformPrompts.relationship_map(request.entityName)
            replacements = {
                "{{one_to_many_primary}}": one_to_many_primary,
                "{{one_to_many_related}}": one_to_many_related,
                "{{many_to_many}}": many_to_many
            }
        
        # Replace all placeholders in the template
        for placeholder, value in replacements.items():
            prompt_content = prompt_content.replace(placeholder, value)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": prompt_content
                }
            ]
        }
    except Exception as e:
        print(f"Error using PowerPlatform prompt: {e}", file=sys.stderr)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to use PowerPlatform prompt: {str(e)}"
                }
            ]
        }

async def main():
    server = McpServer()
    
    # Register handlers
    server.register_handler("get-entity-metadata", handle_get_entity_metadata)
    server.register_handler("get-entity-attributes", handle_get_entity_attributes)
    server.register_handler("get-entity-attribute", handle_get_entity_attribute)
    server.register_handler("get-entity-relationships", handle_get_entity_relationships)
    server.register_handler("get-global-option-set", handle_get_global_option_set)
    server.register_handler("get-record", handle_get_record)
    server.register_handler("query-records", handle_query_records)
    server.register_handler("use-powerplatform-prompt", handle_use_powerplatform_prompt)
    
    print("Initializing PowerPlatform MCP Server...", file=sys.stderr)
    await server.start()

if __name__ == "__main__":
    asyncio.run(main()) 