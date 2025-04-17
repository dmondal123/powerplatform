from setuptools import setup, find_packages

setup(
    name="powerplatform-mcp",
    version="1.0.0",
    description="A Model Context Protocol (MCP) server for PowerPlatform/Dataverse",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        "pydantic",
        "msal",
        "requests",
        "asyncio"
    ],
    entry_points={
        "console_scripts": [
            "powerplatform-mcp=main_entry:main_entry",
        ],
    },
    python_requires=">=3.7",
) 