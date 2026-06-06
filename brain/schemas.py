from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class ToolCall(BaseModel):
    tool_name: str = Field(description="The exact name of the tool to execute.")
    arguments: Dict[str, Any] = Field(description="The arguments to pass to the tool.")
    reasoning: Optional[str] = Field(default=None, description="The reasoning behind selecting this tool.")

class Plan(BaseModel):
    speech: str = Field(description="The conversational text to speak to the user.")
    tool_calls: List[ToolCall] = Field(description="A list of tools to execute. Must be length 1 for state-dependent actions.")

class VerificationResult(BaseModel):
    success: bool = Field(description="True if the goal was objectively achieved.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")
    evidence: str = Field(description="A human-readable string explaining why it succeeded or failed.")
    verification_time: float = Field(description="Time taken to verify in seconds.")

class Task(BaseModel):
    task_id: str
    created_at: float
    tool_call: ToolCall
    status: str = "queued"
    attempts: int = 0
    verification_result: Optional[VerificationResult] = None
    priority: int = 1
    context_snapshot: Optional[Any] = None

class ContextSnapshot(BaseModel):
    timestamp: float = Field(description="When this snapshot was taken.")
    active_window: Optional[str] = Field(default=None, description="Title of the active window.")
    active_process: Optional[str] = Field(default=None, description="Name of the active process.")
    clipboard: Optional[str] = Field(default=None, description="Current clipboard contents.")
    current_folder: Optional[str] = Field(default=None, description="Current working directory or explorer path.")

