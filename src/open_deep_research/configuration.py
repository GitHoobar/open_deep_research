from pydantic import BaseModel, Field
from typing import Any, List, Optional
from langchain_core.runnables import RunnableConfig
import os
from enum import Enum



class Configuration(BaseModel):
    # General Configuration
    max_structured_output_retries: int = Field(
        default=3,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 3,
                "min": 1,
                "max": 10,
                "description": "Maximum number of retries for structured output calls from models"
            }
        }
    )
    allow_clarification: bool = Field(
        default=True,
        metadata={
            "x_oap_ui_config": {
                "type": "boolean",
                "default": True,
                "description": "Whether to allow the agent to ask the user clarifying questions before starting analysis"
            }
        }
    )
    max_concurrent_analysis_units: int = Field(
        default=6,  # Increased for deeper parallel analysis
        metadata={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 6,
                "min": 1,
                "max": 20,
                "step": 1,
                "description": "Maximum number of analysis units to run concurrently. This will allow the agent to use multiple sub-agents to analyze different aspects of the repository. Note: with more concurrency, you may run into rate limits."
            }
        }
    )
    # Analysis Configuration
    max_analyzer_iterations: int = Field(
        default=15,  # Increased for more thorough research
        metadata={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 15,
                "min": 1,
                "max": 25,
                "step": 1,
                "description": "Maximum number of analysis iterations for the Analysis Supervisor. This is the number of times the Analysis Supervisor will reflect on the analysis and ask follow-up questions."
            }
        }
    )
    max_react_tool_calls: int = Field(
        default=5,
        metadata={
            "x_oap_ui_config": {
                "type": "slider",
                "default": 5,
                "min": 1,
                "max": 30,
                "step": 1,
                "description": "Maximum number of tool calling iterations to make in a single analyzer step."
            }
        }
    )
    # Model Configuration
    analysis_model: str = Field(
        default="openai:gpt-4.1",
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "default": "openai:gpt-4.1",
                "description": "Model for conducting repository analysis and code understanding"
            }
        }
    )
    analysis_model_max_tokens: int = Field(
        default=10000,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 10000,
                "description": "Maximum output tokens for analysis model"
            }
        }
    )
    compression_model: str = Field(
        default="openai:gpt-4.1-mini",
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "default": "openai:gpt-4.1-mini",
                "description": "Model for compressing analysis findings from sub-agents"
            }
        }
    )
    compression_model_max_tokens: int = Field(
        default=8192,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 8192,
                "description": "Maximum output tokens for compression model"
            }
        }
    )
    final_design_doc_model: str = Field(
        default="openai:gpt-4.1",
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "default": "openai:gpt-4.1",
                "description": "Model for writing the final design document from all analysis findings"
            }
        }
    )
    final_design_doc_model_max_tokens: int = Field(
        default=10000,
        metadata={
            "x_oap_ui_config": {
                "type": "number",
                "default": 10000,
                "description": "Maximum output tokens for final design document model"
            }
        }
    )
    # GitHub Configuration
    github_repository: Optional[str] = Field(
        default=None,
        optional=True,
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "description": "Default GitHub repository to analyze (format: owner/repo). Can be overridden by user input."
            }
        }
    )
    github_app_id: Optional[str] = Field(
        default=None,
        optional=True,
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "description": "GitHub App ID for accessing private repositories"
            }
        }
    )
    github_app_private_key: Optional[str] = Field(
        default=None,
        optional=True,
        metadata={
            "x_oap_ui_config": {
                "type": "text",
                "description": "GitHub App private key file path or content"
            }
        }
    )



    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        return cls(**{k: v for k, v in values.items() if v is not None})

    class Config:
        arbitrary_types_allowed = True