from typing import Annotated, Optional
from pydantic import BaseModel, Field
import operator
from langgraph.graph import MessagesState
from langchain_core.messages import MessageLikeRepresentation
from typing_extensions import TypedDict

###################
# Structured Outputs
###################
class AnalyzeRepository(BaseModel):
    """Call this tool to analyze a specific aspect of the repository."""
    analysis_topic: str = Field(
        description="The specific aspect of the repository to analyze. Should be a single topic, and should be described in high detail (at least a paragraph).",
    )

class AnalysisComplete(BaseModel):
    """Call this tool to indicate that the repository analysis is complete."""

class Summary(BaseModel):
    summary: str
    key_excerpts: str

class ClarifyWithUser(BaseModel):
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the design doc scope",
    )
    verification: str = Field(
        description="Verify message that we will start analysis after the user has provided the necessary information.",
    )

class DesignDocQuery(BaseModel):
    repo_url: str = Field(
        description="The GitHub repository URL to analyze.",
    )
    design_brief: str = Field(
        description="A brief description of what design document should be created based on the repository analysis.",
    )


###################
# State Definitions
###################

def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
    
class AgentInputState(MessagesState):
    """InputState is only 'messages'"""

class AgentState(MessagesState):
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    repo_url: Optional[str]
    design_brief: Optional[str]
    raw_analysis: Annotated[list[str], override_reducer] = []
    analysis_notes: Annotated[list[str], override_reducer] = []
    final_design_doc: str

class SupervisorState(TypedDict):
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    repo_url: str
    design_brief: str
    analysis_notes: Annotated[list[str], override_reducer] = []
    analysis_iterations: int = 0
    raw_analysis: Annotated[list[str], override_reducer] = []

class AnalyzerState(TypedDict):
    analyzer_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int = 0
    analysis_topic: str
    compressed_analysis: str
    raw_analysis: Annotated[list[str], override_reducer] = []

class AnalyzerOutputState(BaseModel):
    compressed_analysis: str
    raw_analysis: Annotated[list[str], override_reducer] = []