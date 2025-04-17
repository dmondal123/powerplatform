import os
import json
import requests
import msal
from datetime import datetime, timedelta

class PowerPlatformConfig:
    def __init__(self, organization_url, client_id, client_secret, tenant_id):
        self.organization_url = organization_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id

class PowerPlatformService:
    def __init__(self, config):
        self.config = config
        self.access_token = None
        self.token_expiration_time = 0
        
        # Initialize MSAL client
        self.msal_client = msal.ConfidentialClientApplication(
            client_id=self.config.client_id,
            client_credential=self.config.client_secret,
            authority=f"https://login.microsoftonline.com/{self.config.tenant_id}"
        )
    
    async def get_access_token(self):
        """Get an access token for the PowerPlatform API"""
        current_time = datetime.now().timestamp()
        
        # If we have a token that isn't expired, return it
        if self.access_token and self.token_expiration_time > current_time:
            return self.access_token
        
        try:
            # Get a new token
            result = self.msal_client.acquire_token_for_client(
                scopes=[f"{self.config.organization_url}/.default"]
            )
            
            if not result or "access_token" not in result:
                raise Exception("Failed to acquire access token")
            
            self.access_token = result["access_token"]
            
            # Set expiration time (subtract 5 minutes to refresh early)
            if "expires_in" in result:
                self.token_expiration_time = current_time + result["expires_in"] - (5 * 60)
            
            return self.access_token
        except Exception as e:
            print(f"Error acquiring access token: {e}")
            raise Exception("Authentication failed")
    
    async def make_request(self, endpoint):
        """Make an authenticated request to the PowerPlatform API"""
        try:
            token = await self.get_access_token()
            
            response = requests.get(
                f"{self.config.organization_url}/{endpoint}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "OData-MaxVersion": "4.0",
                    "OData-Version": "4.0"
                }
            )
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"PowerPlatform API request failed: {e}")
            raise Exception(f"PowerPlatform API request failed: {e}")
    
    async def get_entity_metadata(self, entity_name):
        """Get metadata about an entity"""
        response = await self.make_request(f"api/data/v9.2/EntityDefinitions(LogicalName='{entity_name}')")
        
        # Remove Privileges property if it exists
        if response and isinstance(response, dict) and "Privileges" in response:
            del response["Privileges"]
        
        return response
    
    async def get_entity_attributes(self, entity_name):
        """Get metadata about entity attributes/fields"""
        select_properties = "LogicalName"
        
        # Make the request to get attributes
        response = await self.make_request(
            f"api/data/v9.2/EntityDefinitions(LogicalName='{entity_name}')/Attributes?$select={select_properties}&$filter=AttributeType ne 'Virtual'"
        )
        
        if response and "value" in response:
            # First pass: Filter out attributes that end with 'yominame'
            response["value"] = [
                attribute for attribute in response["value"] 
                if not attribute.get("LogicalName", "").endswith("yominame")
            ]
            
            # Filter out attributes that end with 'name' if there is another attribute with the same name without the 'name' suffix
            base_names = set()
            names_attributes = {}
            
            for attribute in response["value"]:
                logical_name = attribute.get("LogicalName", "")
                
                if logical_name.endswith("name") and len(logical_name) > 4:
                    base_name = logical_name[:-4]  # Remove 'name' suffix
                    names_attributes[base_name] = attribute
                else:
                    # This is a potential base attribute
                    base_names.add(logical_name)
            
            # Find attributes to remove that match the pattern
            attributes_to_remove = set()
            for base_name, name_attribute in names_attributes.items():
                if base_name in base_names:
                    attributes_to_remove.add(name_attribute["LogicalName"])
            
            response["value"] = [
                attribute for attribute in response["value"] 
                if attribute.get("LogicalName") not in attributes_to_remove
            ]
        
        return response
    
    async def get_entity_attribute(self, entity_name, attribute_name):
        """Get metadata about a specific entity attribute/field"""
        return await self.make_request(
            f"api/data/v9.2/EntityDefinitions(LogicalName='{entity_name}')/Attributes(LogicalName='{attribute_name}')"
        )
    
    async def get_entity_one_to_many_relationships(self, entity_name):
        """Get one-to-many relationships for an entity"""
        select_properties = [
            "SchemaName",
            "RelationshipType",
            "ReferencedAttribute",
            "ReferencedEntity",
            "ReferencingAttribute",
            "ReferencingEntity",
            "ReferencedEntityNavigationPropertyName",
            "ReferencingEntityNavigationPropertyName"
        ]
        select_str = ",".join(select_properties)
        
        # Only filter by ReferencingAttribute in the OData query since startswith isn't supported
        response = await self.make_request(
            f"api/data/v9.2/EntityDefinitions(LogicalName='{entity_name}')/OneToManyRelationships?$select={select_str}&$filter=ReferencingAttribute ne 'regardingobjectid'"
        )
        
        # Filter the response to exclude relationships with ReferencingEntity starting with 'msdyn_' or 'adx_'
        if response and "value" in response:
            response["value"] = [
                relationship for relationship in response["value"]
                if not (relationship.get("ReferencingEntity", "").startswith("msdyn_") or 
                        relationship.get("ReferencingEntity", "").startswith("adx_"))
            ]
        
        return response
    
    async def get_entity_many_to_many_relationships(self, entity_name):
        """Get many-to-many relationships for an entity"""
        select_properties = [
            "SchemaName",
            "RelationshipType",
            "Entity1LogicalName",
            "Entity2LogicalName",
            "Entity1IntersectAttribute",
            "Entity2IntersectAttribute",
            "Entity1NavigationPropertyName",
            "Entity2NavigationPropertyName"
        ]
        select_str = ",".join(select_properties)
        
        return await self.make_request(
            f"api/data/v9.2/EntityDefinitions(LogicalName='{entity_name}')/ManyToManyRelationships?$select={select_str}"
        )
    
    async def get_entity_relationships(self, entity_name):
        """Get all relationships (one-to-many and many-to-many) for an entity"""
        one_to_many = await self.get_entity_one_to_many_relationships(entity_name)
        many_to_many = await self.get_entity_many_to_many_relationships(entity_name)
        
        return {
            "oneToMany": one_to_many,
            "manyToMany": many_to_many
        }
    
    async def get_global_option_set(self, option_set_name):
        """Get a global option set definition by name"""
        return await self.make_request(
            f"api/data/v9.2/GlobalOptionSetDefinitions(Name='{option_set_name}')"
        )
    
    async def get_record(self, entity_name_plural, record_id):
        """Get a specific record by entity name (plural) and ID"""
        return await self.make_request(
            f"api/data/v9.2/{entity_name_plural}({record_id})"
        )
    
    async def query_records(self, entity_name_plural, filter_expr, max_records=50):
        """Query records using entity name (plural) and a filter expression"""
        from urllib.parse import quote
        encoded_filter = quote(filter_expr)
        return await self.make_request(
            f"api/data/v9.2/{entity_name_plural}?$filter={encoded_filter}&$top={max_records}"
        ) 