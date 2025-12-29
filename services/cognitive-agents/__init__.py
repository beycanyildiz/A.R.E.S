"""Cognitive Agents - LLM-based Decision Making and Exploit Synthesis"""

from .agent_framework import (
    CognitiveAgentOrchestrator,
    OrchestratorAgent,
    PlannerAgent,
    CriticAgent,
    AgentState,
    AgentRole
)

from .exploit_synthesizer import (
    ExploitSynthesizer,
    VulnerabilityContext,
    ExploitCode,
    ExploitLanguage,
    ObfuscationTechnique
)

from .reinforcement_learning import (
    ReinforcementLearningLoop,
    ExploitAttempt,
    OutcomeType,
    RewardFunction
)

from .integrated_pipeline import (
    IntegratedCognitivePipeline,
    MissionConfig
)

__all__ = [
    # Agent Framework
    "CognitiveAgentOrchestrator",
    "OrchestratorAgent",
    "PlannerAgent",
    "CriticAgent",
    "AgentState",
    "AgentRole",
    
    # Exploit Synthesizer
    "ExploitSynthesizer",
    "VulnerabilityContext",
    "ExploitCode",
    "ExploitLanguage",
    "ObfuscationTechnique",
    
    # Reinforcement Learning
    "ReinforcementLearningLoop",
    "ExploitAttempt",
    "OutcomeType",
    "RewardFunction",
    
    # Integrated Pipeline
    "IntegratedCognitivePipeline",
    "MissionConfig",
]
