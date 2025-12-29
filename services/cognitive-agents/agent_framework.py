"""
Cognitive Agents Framework - LLM-based Decision Making

This module implements the "Mixture of Experts" architecture:
- Orchestrator Agent: High-level strategy and task delegation
- Planner Agent: Tactical planning using Chain/Tree of Thoughts
- Critic Agent: Code validation and self-correction
- Executor Agent: Action execution and feedback

Architecture:
- LangGraph for state machine management
- Multiple LLM providers (GPT-4, Claude, Local Llama)
- RAG integration with Vector DB
- Reinforcement learning from outcomes
"""

import os
import logging
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import tiktoken

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Agent roles in the system"""
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    CRITIC = "critic"
    EXECUTOR = "executor"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVISION = "needs_revision"


@dataclass
class AgentState:
    """Shared state between agents"""
    mission_id: str
    target: str
    current_phase: str = "reconnaissance"
    
    # Context accumulation
    recon_data: Dict[str, Any] = field(default_factory=dict)
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    exploit_attempts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Agent outputs
    strategy: Optional[str] = None
    tactical_plan: Optional[Dict[str, Any]] = None
    generated_code: Optional[str] = None
    critique: Optional[str] = None
    
    # Execution results
    execution_result: Optional[Dict[str, Any]] = None
    success: bool = False
    
    # Conversation history
    messages: List[Any] = field(default_factory=list)
    
    # Metadata
    iteration_count: int = 0
    max_iterations: int = 5
    created_at: datetime = field(default_factory=datetime.now)


class LLMProvider:
    """Manages multiple LLM providers with fallback"""
    
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.google_key = os.getenv("GOOGLE_API_KEY")
        
        # Initialize models
        self.models = {}
        
        if self.openai_key:
            self.models["gpt-4o"] = ChatOpenAI(
                model="gpt-4o",
                temperature=0.7,
                api_key=self.openai_key
            )
            self.models["gpt-4o-mini"] = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.7,
                api_key=self.openai_key
            )
        
        if self.google_key:
            # Gemini 2.0 Flash Experimental - Fastest & newest model!
            self.models["gemini-2.0-flash-exp"] = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                temperature=0.7,
                google_api_key=self.google_key,
                convert_system_message_to_human=True  # Gemini compatibility
            )
        
        logger.info(f"Initialized LLM providers: {list(self.models.keys())}")
    
    def get_model(self, model_name: str = "gpt-4o"):
        """Get LLM model with fallback"""
        if model_name in self.models:
            return self.models[model_name]
        
        # Fallback to any available model
        if self.models:
            fallback = list(self.models.values())[0]
            logger.warning(f"Model {model_name} not available, using fallback")
            return fallback
        
        raise ValueError("No LLM models available. Set OPENAI_API_KEY or GOOGLE_API_KEY")
    
    def count_tokens(self, text: str, model: str = "gpt-4") -> int:
        """Count tokens for cost estimation"""
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            # Rough estimate: 1 token ≈ 4 characters
            return len(text) // 4


class OrchestratorAgent:
    """
    High-level strategy agent
    
    Responsibilities:
    - Analyze target and define overall strategy
    - Delegate tasks to specialized agents
    - Make go/no-go decisions
    """
    
    SYSTEM_PROMPT = """You are the Orchestrator Agent in A.R.E.S., an autonomous penetration testing system.

Your role:
1. Analyze the target and reconnaissance data
2. Define the overall attack strategy
3. Identify the most promising attack vectors
4. Delegate specific tasks to specialized agents

You must think like a senior Red Team leader:
- Prioritize stealth and operational security
- Consider detection risks
- Plan for contingencies
- Balance speed vs. thoroughness

Output format:
{
    "strategy": "Brief description of overall approach",
    "priority_targets": ["target1", "target2"],
    "attack_vectors": ["vector1", "vector2"],
    "risk_level": "low|medium|high",
    "next_action": "specific task for Planner Agent"
}

Be concise and tactical."""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider.get_model("gpt-4o")
        self.role = AgentRole.ORCHESTRATOR
    
    async def analyze(self, state: AgentState) -> AgentState:
        """Analyze situation and define strategy"""
        logger.info(f"[{self.role}] Analyzing mission: {state.mission_id}")
        
        # Build context
        context = f"""
Target: {state.target}
Phase: {state.current_phase}

Reconnaissance Data:
{state.recon_data}

Vulnerabilities Found:
{state.vulnerabilities}

Previous Exploit Attempts:
{len(state.exploit_attempts)} attempts
"""
        
        # Create prompt
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"Analyze this situation and provide strategic guidance:\n\n{context}")
        ]
        
        # Get LLM response
        response = await self.llm.ainvoke(messages)
        
        # Update state
        state.strategy = response.content
        state.messages.append({
            "role": self.role,
            "content": response.content,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"[{self.role}] Strategy defined")
        return state


class PlannerAgent:
    """
    Tactical planning agent using Chain of Thought (CoT) and Tree of Thoughts (ToT)
    
    Responsibilities:
    - Break down strategy into actionable steps
    - Generate attack trees with multiple paths
    - Simulate outcomes of different approaches
    - Select optimal path
    """
    
    SYSTEM_PROMPT = """You are the Planner Agent in A.R.E.S., an autonomous penetration testing system.

Your role:
1. Receive strategic objectives from Orchestrator
2. Use Chain of Thought (CoT) reasoning to break down the task
3. Generate multiple tactical approaches (Tree of Thoughts)
4. Evaluate each approach for success probability
5. Select the optimal path

Reasoning process:
Step 1: Understand the objective
Step 2: List all possible approaches
Step 3: For each approach, simulate the steps
Step 4: Identify potential failures
Step 5: Rank approaches by success probability
Step 6: Select best approach

Output format:
{
    "objective": "What we're trying to achieve",
    "approaches": [
        {
            "name": "Approach 1",
            "steps": ["step1", "step2"],
            "success_probability": 0.8,
            "risks": ["risk1"]
        }
    ],
    "selected_approach": "Approach 1",
    "detailed_plan": {
        "steps": [
            {
                "action": "specific action",
                "expected_outcome": "what should happen",
                "fallback": "what to do if it fails"
            }
        ]
    }
}

Think step-by-step and show your reasoning."""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider.get_model("gemini-2.0-flash-exp")  # Gemini 2.0 - fastest!
        self.role = AgentRole.PLANNER
    
    async def plan(self, state: AgentState) -> AgentState:
        """Generate tactical plan using CoT/ToT"""
        logger.info(f"[{self.role}] Planning tactics for mission: {state.mission_id}")
        
        # Build context
        context = f"""
Strategy from Orchestrator:
{state.strategy}

Available Data:
- Target: {state.target}
- Vulnerabilities: {len(state.vulnerabilities)} found
- Previous attempts: {len(state.exploit_attempts)}

Your task: Create a detailed tactical plan to execute the strategy.
"""
        
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=context)
        ]
        
        # Get LLM response
        response = await self.llm.ainvoke(messages)
        
        # Parse plan (in production, use structured output)
        state.tactical_plan = {
            "raw_plan": response.content,
            "created_by": self.role,
            "timestamp": datetime.now().isoformat()
        }
        
        state.messages.append({
            "role": self.role,
            "content": response.content,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"[{self.role}] Tactical plan created")
        return state


class CriticAgent:
    """
    Code validation and self-correction agent
    
    Responsibilities:
    - Review generated exploit code
    - Identify syntax errors, logic flaws
    - Predict detection probability
    - Suggest improvements
    - Approve or reject code
    """
    
    SYSTEM_PROMPT = """You are the Critic Agent in A.R.E.S., an autonomous penetration testing system.

Your role is to be the "devil's advocate" - critically analyze everything:

1. Code Review:
   - Check for syntax errors
   - Identify logic flaws
   - Verify exploit will work as intended

2. Security Analysis:
   - Will this trigger IDS/IPS?
   - Will this trigger WAF?
   - Is the payload obfuscated enough?

3. Operational Security:
   - Are we leaving traces?
   - Can this be attributed back?
   - Is there a safer alternative?

Output format:
{
    "approved": true/false,
    "severity_issues": ["critical issue 1"],
    "warnings": ["warning 1"],
    "suggestions": ["improvement 1"],
    "detection_risk": "low|medium|high",
    "revised_code": "improved version (if applicable)"
}

Be harsh but constructive. Safety and stealth are paramount."""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider.get_model("gpt-4o")
        self.role = AgentRole.CRITIC
    
    async def critique(self, state: AgentState) -> AgentState:
        """Critique generated code or plan"""
        logger.info(f"[{self.role}] Reviewing code for mission: {state.mission_id}")
        
        if not state.generated_code:
            logger.warning(f"[{self.role}] No code to review")
            return state
        
        context = f"""
Review this exploit code:

```python
{state.generated_code}
```

Target context:
- Target: {state.target}
- Vulnerability: {state.vulnerabilities[0] if state.vulnerabilities else 'Unknown'}

Provide detailed critique.
"""
        
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=context)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        state.critique = response.content
        state.messages.append({
            "role": self.role,
            "content": response.content,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"[{self.role}] Critique completed")
        return state


class CognitiveAgentOrchestrator:
    """
    Orchestrates the multi-agent workflow using LangGraph
    """
    
    def __init__(self):
        self.llm_provider = LLMProvider()
        
        # Initialize agents
        self.orchestrator = OrchestratorAgent(self.llm_provider)
        self.planner = PlannerAgent(self.llm_provider)
        self.critic = CriticAgent(self.llm_provider)
        
        # Build state graph
        self.graph = self._build_graph()
        
        logger.info("Cognitive Agent Orchestrator initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph state machine"""
        
        # Define workflow
        workflow = StateGraph(AgentState)
        
        # Add nodes (agents)
        workflow.add_node("orchestrator", self.orchestrator.analyze)
        workflow.add_node("planner", self.planner.plan)
        workflow.add_node("critic", self.critic.critique)
        
        # Define edges (flow)
        workflow.set_entry_point("orchestrator")
        workflow.add_edge("orchestrator", "planner")
        workflow.add_edge("planner", "critic")
        
        # Conditional edge: critic approves or loops back
        def should_continue(state: AgentState) -> Literal["end", "planner"]:
            if state.iteration_count >= state.max_iterations:
                return "end"
            
            # Check if critic approved (simplified)
            if state.critique and "approved" in state.critique.lower():
                return "end"
            
            state.iteration_count += 1
            return "planner"
        
        workflow.add_conditional_edges(
            "critic",
            should_continue,
            {
                "end": END,
                "planner": "planner"
            }
        )
        
        # Compile with memory
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
    
    async def execute_mission(self, mission_id: str, target: str, recon_data: Dict[str, Any]) -> AgentState:
        """Execute cognitive agent workflow"""
        logger.info(f"Starting cognitive agent workflow for mission: {mission_id}")
        
        # Initialize state
        initial_state = AgentState(
            mission_id=mission_id,
            target=target,
            recon_data=recon_data
        )
        
        # Run graph
        config = {"configurable": {"thread_id": mission_id}}
        
        final_state = None
        async for state in self.graph.astream(initial_state, config):
            logger.info(f"State update: {list(state.keys())}")
            final_state = list(state.values())[0]
        
        logger.info(f"Cognitive workflow completed for mission: {mission_id}")
        return final_state


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Initialize orchestrator
        cog_orch = CognitiveAgentOrchestrator()
        
        # Example mission
        recon_data = {
            "hosts": [
                {"ip": "192.168.1.10", "os": "Ubuntu 22.04", "open_ports": [22, 80, 443]}
            ],
            "services": [
                {"port": 80, "service": "nginx", "version": "1.18.0"}
            ]
        }
        
        # Execute
        result = await cog_orch.execute_mission(
            mission_id="test-001",
            target="192.168.1.10",
            recon_data=recon_data
        )
        
        print("\n=== Mission Results ===")
        print(f"Strategy: {result.strategy}")
        print(f"Plan: {result.tactical_plan}")
        print(f"Critique: {result.critique}")
        print(f"Iterations: {result.iteration_count}")
    
    asyncio.run(main())
