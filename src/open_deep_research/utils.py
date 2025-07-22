import os
import asyncio
import logging
import requests
import base64
import json
from datetime import datetime
from typing import Annotated, List, Literal, Dict, Optional, Any
from langchain_core.tools import BaseTool, StructuredTool, tool, ToolException, InjectedToolArg
from langchain_core.messages import HumanMessage, AIMessage, MessageLikeRepresentation, filter_messages
from langchain_core.runnables import RunnableConfig
from langchain_core.language_models import BaseChatModel
from langchain.chat_models import init_chat_model


from langchain_community.utilities.github import GitHubAPIWrapper
from langchain_community.agent_toolkits.github.toolkit import GitHubToolkit
from open_deep_research.state import Summary, AnalysisComplete
from open_deep_research.configuration import Configuration


##########################
# GitHub Repository Analysis Utils
##########################
GITHUB_ANALYSIS_DESCRIPTION = (
    "A comprehensive toolkit for analyzing GitHub repositories. "
    "Useful for understanding codebase structure, reading files, and analyzing repository content."
)

async def comprehensive_repo_analysis(repo_url: str, github_token: str, github_repository: str) -> str:
    """Perform comprehensive repository analysis to understand architecture and technology stack."""
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        
        # Get repository information
        repo_response = requests.get(f"https://api.github.com/repos/{github_repository}", headers=headers)
        if repo_response.status_code != 200:
            return f"Error accessing repository: {repo_response.status_code}"
        
        repo_info = repo_response.json()
        
        # Get repository contents (root level)
        contents_response = requests.get(f"https://api.github.com/repos/{github_repository}/contents", headers=headers)
        if contents_response.status_code != 200:
            return f"Error accessing repository contents: {contents_response.status_code}"
        
        contents = contents_response.json()
        
        # Analyze file structure
        analysis = f"# Repository Analysis: {github_repository}\n\n"
        analysis += f"**Description**: {repo_info.get('description', 'No description')}\n"
        analysis += f"**Language**: {repo_info.get('language', 'Not specified')}\n"
        analysis += f"**Size**: {repo_info.get('size', 0)} KB\n\n"
        
        # Categorize files by type
        config_files = []
        source_files = []
        documentation = []
        notebooks = []
        directories = []
        
        for item in contents:
            name = item['name']
            if item['type'] == 'dir':
                directories.append(name)
            elif name.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb')):
                source_files.append(name)
            elif name.endswith(('.ipynb',)):
                notebooks.append(name)
            elif name.endswith(('.md', '.txt', '.rst', '.doc')):
                documentation.append(name)
            elif name in ['requirements.txt', 'package.json', 'pyproject.toml', 'setup.py', 'Dockerfile', '.gitignore', 'Makefile']:
                config_files.append(name)
        
        analysis += "## Project Structure:\n"
        if directories:
            analysis += f"**Directories**: {', '.join(directories)}\n"
        if source_files:
            analysis += f"**Source Files**: {', '.join(source_files)}\n"
        if notebooks:
            analysis += f"**Jupyter Notebooks**: {', '.join(notebooks)}\n"
        if config_files:
            analysis += f"**Configuration Files**: {', '.join(config_files)}\n"
        if documentation:
            analysis += f"**Documentation**: {', '.join(documentation)}\n"
        
        # Detect technology stack
        tech_indicators = []
        if any(f.endswith('.py') for f in source_files) or 'requirements.txt' in config_files or 'pyproject.toml' in config_files:
            tech_indicators.append("Python")
        if notebooks:
            tech_indicators.append("Jupyter Notebooks")
        if 'package.json' in config_files:
            tech_indicators.append("Node.js/JavaScript")
        if 'Dockerfile' in config_files:
            tech_indicators.append("Docker")
        
        if tech_indicators:
            analysis += f"\n**Detected Technologies**: {', '.join(tech_indicators)}\n"
        
        return analysis
        
    except Exception as e:
        return f"Error during repository analysis: {str(e)}"

async def smart_file_reader(github_token: str, github_repository: str, file_path: str) -> str:
    """Read a file with intelligent context and analysis."""
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        
        # Get file content
        file_response = requests.get(f"https://api.github.com/repos/{github_repository}/contents/{file_path}", headers=headers)
        if file_response.status_code != 200:
            return f"Error reading file {file_path}: {file_response.status_code}"
        
        file_data = file_response.json()
        
        if file_data.get('type') != 'file':
            return f"{file_path} is not a file"
        
        # Decode file content
        content = base64.b64decode(file_data['content']).decode('utf-8')
        
        # Provide context based on file type
        file_ext = file_path.split('.')[-1].lower() if '.' in file_path else ''
        analysis = f"# File Analysis: {file_path}\n\n"
        
        if file_ext == 'py':
            analysis += "**Type**: Python source file\n"
            # Analyze Python imports and structure
            lines = content.split('\n')
            imports = [line.strip() for line in lines if line.strip().startswith(('import ', 'from '))]
            classes = [line.strip() for line in lines if line.strip().startswith('class ')]
            functions = [line.strip() for line in lines if line.strip().startswith('def ')]
            
            if imports:
                analysis += f"**Imports** ({len(imports)}): {', '.join(imports[:5])}{'...' if len(imports) > 5 else ''}\n"
            if classes:
                analysis += f"**Classes** ({len(classes)}): {', '.join([c.split('(')[0].replace('class ', '') for c in classes[:3]])}{'...' if len(classes) > 3 else ''}\n"
            if functions:
                analysis += f"**Functions** ({len(functions)}): {', '.join([f.split('(')[0].replace('def ', '') for f in functions[:5]])}{'...' if len(functions) > 5 else ''}\n"
        
        elif file_ext == 'ipynb':
            analysis += "**Type**: Jupyter Notebook\n"
            try:
                notebook = json.loads(content)
                cells = notebook.get('cells', [])
                code_cells = [c for c in cells if c.get('cell_type') == 'code']
                markdown_cells = [c for c in cells if c.get('cell_type') == 'markdown']
                analysis += f"**Total Cells**: {len(cells)} (Code: {len(code_cells)}, Markdown: {len(markdown_cells)})\n"
            except:
                analysis += "**Note**: Could not parse notebook structure\n"
        
        elif file_path.lower() in ['readme.md', 'readme.txt', 'readme.rst']:
            analysis += "**Type**: Project README/Documentation\n"
        
        elif file_path in ['requirements.txt', 'pyproject.toml', 'setup.py']:
            analysis += "**Type**: Python dependency/configuration file\n"
        
        analysis += f"\n**File Size**: {len(content)} characters\n"
        analysis += f"\n## File Content:\n```{file_ext}\n{content}\n```"
        
        return analysis
        
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"

async def intelligent_code_search(github_token: str, github_repository: str, query: str, file_extension: str = "") -> str:
    """Search for code patterns with intelligent context."""
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        
        # Build search query
        search_query = f"{query} repo:{github_repository}"
        if file_extension:
            search_query += f" extension:{file_extension}"
        
        # Use GitHub search API
        search_response = requests.get(
            f"https://api.github.com/search/code?q={requests.utils.quote(search_query)}&per_page=10",
            headers=headers
        )
        
        if search_response.status_code != 200:
            return f"Error searching code: {search_response.status_code}"
        
        search_results = search_response.json()
        
        if search_results['total_count'] == 0:
            return f"No code found matching '{query}'"
        
        analysis = f"# Code Search Results for '{query}'\n\n"
        analysis += f"**Total matches**: {search_results['total_count']}\n\n"
        
        for i, item in enumerate(search_results['items'][:5], 1):
            analysis += f"## Result {i}: {item['name']}\n"
            analysis += f"**Path**: {item['path']}\n"
            analysis += f"**Repository**: {item['repository']['full_name']}\n"
            if 'text_matches' in item:
                for match in item['text_matches'][:2]:
                    analysis += f"**Match**: ...{match.get('fragment', 'N/A')}...\n"
            analysis += "\n"
        
        return analysis
        
    except Exception as e:
        return f"Error during code search: {str(e)}"

async def detect_tech_stack(github_token: str, github_repository: str) -> str:
    """Detect and analyze the technology stack used in the repository."""
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        
        # Get languages used in the repository
        languages_response = requests.get(f"https://api.github.com/repos/{github_repository}/languages", headers=headers)
        if languages_response.status_code == 200:
            languages = languages_response.json()
        else:
            languages = {}
        
        analysis = f"# Technology Stack Analysis: {github_repository}\n\n"
        
        if languages:
            total_bytes = sum(languages.values())
            analysis += "## Programming Languages:\n"
            for lang, bytes_count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                percentage = (bytes_count / total_bytes) * 100
                analysis += f"- **{lang}**: {percentage:.1f}% ({bytes_count:,} bytes)\n"
        
        # Check for specific framework/library indicators
        config_files_to_check = [
            ('requirements.txt', 'Python dependencies'),
            ('pyproject.toml', 'Python project configuration'),
            ('setup.py', 'Python package setup'),
            ('package.json', 'Node.js dependencies'),
            ('Dockerfile', 'Docker containerization'),
            ('docker-compose.yml', 'Docker Compose'),
            ('.github/workflows', 'GitHub Actions CI/CD'),
            ('Makefile', 'Build automation'),
            ('environment.yml', 'Conda environment'),
            ('pipfile', 'Pipenv dependencies')
        ]
        
        analysis += "\n## Detected Configuration Files:\n"
        for file_path, description in config_files_to_check:
            file_response = requests.get(f"https://api.github.com/repos/{github_repository}/contents/{file_path}", headers=headers)
            if file_response.status_code == 200:
                analysis += f"- **{file_path}**: {description}\n"
        
        return analysis
        
    except Exception as e:
        return f"Error detecting technology stack: {str(e)}"

async def analyze_config_files(github_token: str, github_repository: str) -> str:
    """Analyze project configuration files to understand dependencies and setup."""
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        
        analysis = f"# Configuration Files Analysis: {github_repository}\n\n"
        
        # Check key configuration files
        config_files = [
            'requirements.txt',
            'pyproject.toml', 
            'setup.py',
            'environment.yml',
            'package.json',
            'Dockerfile'
        ]
        
        for config_file in config_files:
            file_response = requests.get(f"https://api.github.com/repos/{github_repository}/contents/{config_file}", headers=headers)
            if file_response.status_code == 200:
                file_data = file_response.json()
                content = base64.b64decode(file_data['content']).decode('utf-8')
                
                analysis += f"## {config_file}\n"
                
                if config_file == 'requirements.txt':
                    deps = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
                    analysis += f"**Python Dependencies** ({len(deps)}): {', '.join(deps[:10])}{'...' if len(deps) > 10 else ''}\n\n"
                
                elif config_file == 'pyproject.toml':
                    analysis += "**Python Project Configuration**\n"
                    analysis += f"```toml\n{content[:500]}{'...' if len(content) > 500 else ''}\n```\n\n"
                
                elif config_file == 'package.json':
                    try:
                        package_data = json.loads(content)
                        analysis += f"**Project Name**: {package_data.get('name', 'N/A')}\n"
                        analysis += f"**Version**: {package_data.get('version', 'N/A')}\n"
                        if 'dependencies' in package_data:
                            deps = list(package_data['dependencies'].keys())
                            analysis += f"**Dependencies**: {', '.join(deps[:10])}{'...' if len(deps) > 10 else ''}\n"
                    except:
                        analysis += "**Note**: Could not parse package.json\n"
                    analysis += "\n"
                
                else:
                    analysis += f"```\n{content[:300]}{'...' if len(content) > 300 else ''}\n```\n\n"
        
        return analysis
        
    except Exception as e:
        return f"Error analyzing configuration files: {str(e)}"

async def explore_directory_structure(github_token: str, github_repository: str, directory_path: str = "") -> str:
    """Explore a specific directory to understand its organization."""
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        
        # Get directory contents
        url = f"https://api.github.com/repos/{github_repository}/contents"
        if directory_path:
            url += f"/{directory_path.rstrip('/')}"
        
        dir_response = requests.get(url, headers=headers)
        if dir_response.status_code != 200:
            return f"Error accessing directory {directory_path or 'root'}: {dir_response.status_code}"
        
        contents = dir_response.json()
        
        analysis = f"# Directory Structure: {directory_path or 'Root Directory'}\n\n"
        
        # Categorize contents
        directories = []
        python_files = []
        notebooks = []
        config_files = []
        other_files = []
        
        for item in contents:
            name = item['name']
            if item['type'] == 'dir':
                directories.append(name)
            elif name.endswith('.py'):
                python_files.append(name)
            elif name.endswith('.ipynb'):
                notebooks.append(name)
            elif name in ['requirements.txt', 'setup.py', 'pyproject.toml', '.gitignore', 'Dockerfile', 'README.md']:
                config_files.append(name)
            else:
                other_files.append(name)
        
        if directories:
            analysis += f"**Subdirectories** ({len(directories)}): {', '.join(directories)}\n"
        if python_files:
            analysis += f"**Python Files** ({len(python_files)}): {', '.join(python_files)}\n"
        if notebooks:
            analysis += f"**Jupyter Notebooks** ({len(notebooks)}): {', '.join(notebooks)}\n"
        if config_files:
            analysis += f"**Configuration Files** ({len(config_files)}): {', '.join(config_files)}\n"
        if other_files:
            analysis += f"**Other Files** ({len(other_files)}): {', '.join(other_files[:10])}{'...' if len(other_files) > 10 else ''}\n"
        
        return analysis
        
    except Exception as e:
        return f"Error exploring directory: {str(e)}"

async def analyze_dependencies_and_imports(github_token: str, github_repository: str) -> str:
    """Analyze dependencies, imports, and module relationships in the codebase."""
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        
        analysis = f"# Dependency Graph Analysis: {github_repository}\n\n"
        
        # Search for Python import patterns
        import_patterns = [
            "from django",
            "import django", 
            "from rest_framework",
            "import stripe",
            "from .models import",
            "from .views import",
            "from billing",
            "from user"
        ]
        
        dependency_map = {}
        
        for pattern in import_patterns:
            search_response = requests.get(
                f"https://api.github.com/search/code?q={requests.utils.quote(f'{pattern} repo:{github_repository}')}&per_page=10",
                headers=headers
            )
            
            if search_response.status_code == 200:
                results = search_response.json()
                if results['total_count'] > 0:
                    analysis += f"## {pattern} Dependencies\n"
                    for item in results['items'][:3]:
                        file_path = item['path']
                        if file_path not in dependency_map:
                            dependency_map[file_path] = []
                        dependency_map[file_path].append(pattern)
                        analysis += f"- **{file_path}**: Uses {pattern}\n"
                    analysis += "\n"
        
        # Analyze key architectural patterns
        analysis += "## Architectural Dependencies\n"
        for file_path, deps in dependency_map.items():
            if len(deps) > 1:
                analysis += f"- **{file_path}**: Central component using {', '.join(deps)}\n"
        
        return analysis
        
    except Exception as e:
        return f"Error analyzing dependencies: {str(e)}"

async def trace_execution_flow(github_token: str, github_repository: str, entry_point: str) -> str:
    """Trace code execution flow from a starting point."""
    try:
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        
        analysis = f"# Code Flow Analysis: {entry_point}\n\n"
        
        # Extract file and function/class from entry point
        if ":" in entry_point:
            file_path, target = entry_point.split(":", 1)
        else:
            file_path = entry_point
            target = None
        
        # Read the entry point file
        file_response = requests.get(f"https://api.github.com/repos/{github_repository}/contents/{file_path}", headers=headers)
        if file_response.status_code == 200:
            file_data = file_response.json()
            content = base64.b64decode(file_data['content']).decode('utf-8')
            
            analysis += f"## Starting Point: {file_path}\n"
            
            # Find function calls and imports
            lines = content.split('\n')
            imports = [line.strip() for line in lines if line.strip().startswith(('import ', 'from '))]
            
            if target:
                # Find the specific function/class
                in_target = False
                target_lines = []
                for line in lines:
                    if f"def {target}" in line or f"class {target}" in line:
                        in_target = True
                    elif in_target and (line.startswith('def ') or line.startswith('class ') or (line and not line.startswith(' '))):
                        break
                    
                    if in_target:
                        target_lines.append(line)
                
                analysis += f"### Function/Class: {target}\n"
                analysis += f"```python\n" + "\n".join(target_lines[:10]) + "\n```\n\n"
            
            analysis += f"### Imports in {file_path}\n"
            for imp in imports[:5]:
                analysis += f"- {imp}\n"
            
            # Search for function calls within the target
            if target_lines:
                function_calls = []
                for line in target_lines:
                    # Simple pattern matching for function calls
                    if "(" in line and ")" in line:
                        # Extract potential function calls
                        import re
                        calls = re.findall(r'(\w+)\(', line)
                        function_calls.extend(calls)
                
                if function_calls:
                    analysis += f"\n### Function Calls in {target}\n"
                    for call in set(function_calls)[:5]:
                        analysis += f"- {call}()\n"
        
        return analysis
        
    except Exception as e:
        return f"Error tracing code flow: {str(e)}"

async def get_github_tools(config: RunnableConfig):
    """Get enhanced GitHub tools for comprehensive repository analysis."""
    try:
        # Get repository URL from config
        repo_url = config.get("configurable", {}).get("github_repo_url", "")
        github_token = config.get("configurable", {}).get("github_access_token", "")
        
        # Extract owner/repo from URL
        github_repository = None
        if "github.com/" in repo_url:
            parts = repo_url.replace("https://github.com/", "").replace("http://github.com/", "").split("/")
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                github_repository = f"{owner}/{repo}"
        
        if not github_repository or not github_token:
            logging.warning("GitHub repository or token not configured properly")
            return []
        
        # Create enhanced analysis tools
        tools = []
        
        # 1. Repository Structure Analyzer
        @tool
        async def analyze_repository_structure() -> str:
            """Analyze the complete repository structure to understand the codebase architecture, 
            languages, frameworks, and project organization."""
            return await comprehensive_repo_analysis(repo_url, github_token, github_repository)
        
        # 2. Intelligent File Reader
        @tool  
        async def read_file_with_context(file_path: str) -> str:
            """Read a specific file and provide intelligent context about its purpose and relationships.
            
            Args:
                file_path: Path to the file in the repository (e.g., 'src/main.py', 'README.md')
            """
            return await smart_file_reader(github_token, github_repository, file_path)
        
        # 3. Code Pattern Search
        @tool
        async def search_code_patterns(query: str, file_extension: str = "") -> str:
            """Search for specific code patterns, functions, classes, or concepts across the codebase.
            
            Args:
                query: Search term (e.g., 'class User', 'def authenticate', 'import flask')
                file_extension: Optional file extension filter (e.g., 'py', 'js', 'ipynb')
            """
            return await intelligent_code_search(github_token, github_repository, query, file_extension)
        
        # 4. Technology Stack Detector
        @tool
        async def detect_technology_stack() -> str:
            """Detect and analyze the technology stack, frameworks, dependencies, and architecture patterns
            used in the repository."""
            return await detect_tech_stack(github_token, github_repository)
        
        # 5. Project Configuration Analyzer
        @tool
        async def analyze_project_configuration() -> str:
            """Analyze project configuration files (requirements.txt, package.json, pyproject.toml, etc.)
            to understand dependencies, build setup, and project structure."""
            return await analyze_config_files(github_token, github_repository)
        
        # 6. Directory Explorer
        @tool
        async def explore_directory(directory_path: str = "") -> str:
            """Explore a specific directory to understand its contents and organization.
            
            Args:
                directory_path: Path to directory (e.g., 'src/', 'tests/', 'notebooks/') or empty for root
            """
            return await explore_directory_structure(github_token, github_repository, directory_path)
        
        # 7. Dependency Graph Analyzer
        @tool
        async def analyze_dependency_graph() -> str:
            """Analyze dependencies, imports, and module relationships in the codebase to understand how components connect."""
            return await analyze_dependencies_and_imports(github_token, github_repository)
        
        # 8. Code Flow Tracer
        @tool
        async def trace_code_flow(entry_point: str) -> str:
            """Trace code execution flow from a starting point (e.g., API endpoint, function, or class method).
            
            Args:
                entry_point: Starting point to trace (e.g., 'billing/views.py:process_payment', 'user/models.py:User')
            """
            return await trace_execution_flow(github_token, github_repository, entry_point)
        
        tools.extend([
            analyze_repository_structure,
            read_file_with_context,
            search_code_patterns,
            detect_technology_stack,
            analyze_project_configuration,
            explore_directory,
            analyze_dependency_graph,
            trace_code_flow
        ])
        
        return tools
        
    except Exception as e:
        logging.error(f"Error creating enhanced GitHub tools: {e}")
        return []

async def analyze_repository_structure(repo_url: str, config: RunnableConfig) -> str:
    """Analyze the basic structure of a GitHub repository."""
    try:
        # Extract owner/repo from URL
        if "github.com/" in repo_url:
            parts = repo_url.replace("https://github.com/", "").replace("http://github.com/", "").split("/")
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                repo_identifier = f"{owner}/{repo}"
                
                # Set environment variable for GitHub toolkit
                os.environ["GITHUB_REPOSITORY"] = repo_identifier
                
                return f"Repository {repo_identifier} configured for analysis."
            else:
                return f"Invalid GitHub URL format: {repo_url}"
        else:
            return f"Invalid GitHub URL: {repo_url}"
            
    except Exception as e:
        logging.error(f"Error analyzing repository structure: {e}")
        return f"Error analyzing repository: {str(e)}"

async def clone_repository(repo_url: str, target_dir: str = "/tmp/repo_analysis") -> str:
    """Clone a GitHub repository for local analysis."""
    try:
        import subprocess
        import shutil
        
        # Clean up existing directory
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        
        # Clone the repository
        result = subprocess.run(
            ["git", "clone", repo_url, target_dir],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            return f"Successfully cloned repository to {target_dir}"
        else:
            return f"Failed to clone repository: {result.stderr}"
            
    except Exception as e:
        logging.error(f"Error cloning repository: {e}")
        return f"Error cloning repository: {str(e)}"

async def summarize_code_analysis(model: BaseChatModel, analysis_content: str) -> str:
    """Summarize code analysis results."""
    try:
        summary_prompt = f"""
        Analyze the following code/repository information and provide a concise summary:
        
        {analysis_content}
        
        Please provide:
        1. Key architectural patterns identified
        2. Main technologies and frameworks used
        3. Important files and directories
        4. Potential areas for improvement or extension
        
        Format as a structured summary.
        """
        
        summary = await asyncio.wait_for(
            model.ainvoke([HumanMessage(content=summary_prompt)]),
            timeout=60.0
        )
        
        return f"<summary>\n{summary.content}\n</summary>"
        
    except (asyncio.TimeoutError, Exception) as e:
        logging.error(f"Failed to summarize code analysis: {str(e)}")
        return analysis_content





##########################
# Tool Utils
##########################
async def get_all_tools(config: RunnableConfig):
    # Create the AnalysisComplete tool
    analysis_complete_tool = StructuredTool.from_function(
        func=lambda: "Analysis completed",
        name="AnalysisComplete",
        description="Call this tool to indicate that the repository analysis is complete.",
        args_schema=AnalysisComplete
    )
    tools = [analysis_complete_tool]
    
    # Add GitHub analysis tools
    github_tools = await get_github_tools(config)
    tools.extend(github_tools)
    
    return tools

def get_notes_from_tool_calls(messages: list[MessageLikeRepresentation]):
    return [tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")]

def get_today_str() -> str:
    """Get today's date as a string."""
    return datetime.now().strftime("%Y-%m-%d")


##########################
# Token Limit Exceeded Utils (keeping existing)
##########################
def is_token_limit_exceeded(exception: Exception, model_name: str = None) -> bool:
    error_str = str(exception).lower()
    provider = None
    if model_name:
        model_str = str(model_name).lower()
        if model_str.startswith('openai:'):
            provider = 'openai'
        elif model_str.startswith('anthropic:'):
            provider = 'anthropic'
        elif model_str.startswith('gemini:') or model_str.startswith('google:'):
            provider = 'gemini'
    if provider == 'openai':
        return _check_openai_token_limit(exception, error_str)
    elif provider == 'anthropic':
        return _check_anthropic_token_limit(exception, error_str)
    elif provider == 'gemini':
        return _check_gemini_token_limit(exception, error_str)
    
    return (_check_openai_token_limit(exception, error_str) or
            _check_anthropic_token_limit(exception, error_str) or
            _check_gemini_token_limit(exception, error_str))

def _check_openai_token_limit(exception: Exception, error_str: str) -> bool:
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')
    is_openai_exception = ('openai' in exception_type.lower() or 
                          'openai' in module_name.lower())
    is_bad_request = class_name in ['BadRequestError', 'InvalidRequestError']
    if is_openai_exception and is_bad_request:
        token_keywords = ['token', 'context', 'length', 'maximum context', 'reduce']
        if any(keyword in error_str for keyword in token_keywords):
            return True
    if hasattr(exception, 'code') and hasattr(exception, 'type'):
        if (getattr(exception, 'code', '') == 'context_length_exceeded' or
            getattr(exception, 'type', '') == 'invalid_request_error'):
            return True
    return False

def _check_anthropic_token_limit(exception: Exception, error_str: str) -> bool:
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')
    is_anthropic_exception = ('anthropic' in exception_type.lower() or 
                             'anthropic' in module_name.lower())
    is_bad_request = class_name == 'BadRequestError'
    if is_anthropic_exception and is_bad_request:
        if 'prompt is too long' in error_str:
            return True
    return False

def _check_gemini_token_limit(exception: Exception, error_str: str) -> bool:
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')
    
    is_google_exception = ('google' in exception_type.lower() or 'google' in module_name.lower())
    is_resource_exhausted = class_name in ['ResourceExhausted', 'GoogleGenerativeAIFetchError']
    if is_google_exception and is_resource_exhausted:
        return True
    if 'google.api_core.exceptions.resourceexhausted' in exception_type.lower():
        return True
    
    return False

# NOTE: This may be out of date or not applicable to your models. Please update this as needed.
MODEL_TOKEN_LIMITS = {
    "openai:gpt-4.1-mini": 1047576,
    "openai:gpt-4.1-nano": 1047576,
    "openai:gpt-4.1": 1047576,
    "openai:gpt-4o-mini": 128000,
    "openai:gpt-4o": 128000,
    "openai:o4-mini": 200000,
    "openai:o3-mini": 200000,
    "openai:o3": 200000,
    "openai:o3-pro": 200000,
    "openai:o1": 200000,
    "openai:o1-pro": 200000,
    "anthropic:claude-opus-4": 200000,
    "anthropic:claude-sonnet-4": 200000,
    "anthropic:claude-3-7-sonnet": 200000,
    "anthropic:claude-3-5-sonnet": 200000,
    "anthropic:claude-3-5-haiku": 200000,
    "google:gemini-1.5-pro": 2097152,
    "google:gemini-1.5-flash": 1048576,
    "google:gemini-pro": 32768,
    "cohere:command-r-plus": 128000,
    "cohere:command-r": 128000,
    "cohere:command-light": 4096,
    "cohere:command": 4096,
    "mistral:mistral-large": 32768,
    "mistral:mistral-medium": 32768,
    "mistral:mistral-small": 32768,
    "mistral:mistral-7b-instruct": 32768,
    "ollama:codellama": 16384,
    "ollama:llama2:70b": 4096,
    "ollama:llama2:13b": 4096,
    "ollama:llama2": 4096,
    "ollama:mistral": 32768,
}

def get_model_token_limit(model_string):
    for key, token_limit in MODEL_TOKEN_LIMITS.items():
        if key in model_string:
            return token_limit
    return None

def remove_up_to_last_ai_message(messages: list[MessageLikeRepresentation]) -> list[MessageLikeRepresentation]:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            return messages[:i]  # Return everything up to (but not including) the last AI message
    return messages

##########################
# Misc Utils
##########################
def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.now().strftime("%a %b %-d, %Y")

def get_config_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    elif isinstance(value, dict):
        return value
    else:
        return value.value

def get_api_key_for_model(model_name: str, config: RunnableConfig):
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    model_name = model_name.lower()
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        if model_name.startswith("openai:"):
            return api_keys.get("OPENAI_API_KEY")
        elif model_name.startswith("anthropic:"):
            return api_keys.get("ANTHROPIC_API_KEY")
        elif model_name.startswith("google"):
            return api_keys.get("GOOGLE_API_KEY")
        return None
    else:
        if model_name.startswith("openai:"): 
            return os.getenv("OPENAI_API_KEY")
        elif model_name.startswith("anthropic:"):
            return os.getenv("ANTHROPIC_API_KEY")
        elif model_name.startswith("google"):
            return os.getenv("GOOGLE_API_KEY")
        return None

def get_github_token(config: RunnableConfig):
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        return api_keys.get("GITHUB_TOKEN")
    else:
        return os.getenv("GITHUB_TOKEN")