from pydantic import BaseModel, Field
from typing import List, Literal, Optional

AvailableTool = Literal["tavily_search", "save_code_to_file", "calculator", "code_executor", "file_reader"]

class AgentSpec(BaseModel):
    agent_name: str = Field(
        description="Short identifier for the agent, e.g. 'news_summarizer'."
    )
    tools_needed: List[AvailableTool] = Field(
        description="Tools required from the available set."
    )
    task_type: Literal["research", "code_gen"] = Field(
        description="'code_gen' if the user wants code written, 'research' for information retrieval."
    )
    frontend_type: Literal["chat", "dashboard", "form", "results"] = Field(
        description="UI component best suited to display this agent's output."
    )
    requires_web_search: bool = Field(
        description="True if the agent needs real-time web data to answer correctly."
    )
    reasoning: str = Field(
        description="Internal explanation of tool/UI selection. Not exposed to users.",
        exclude=True
    )