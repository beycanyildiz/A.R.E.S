"""
Reinforcement Learning Loop - Learn from Exploit Outcomes

This module implements a feedback loop where the system:
1. Tracks exploit success/failure
2. Analyzes failure patterns
3. Updates strategy based on outcomes
4. Improves future exploit generation

Architecture:
- Experience Replay Buffer (stores past attempts)
- Reward Function (success = +1, failure = -1, partial = 0.5)
- Policy Update (adjusts LLM prompts based on feedback)
- A/B Testing (compares different approaches)
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from collections import deque
import statistics

import redis.asyncio as redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OutcomeType(str, Enum):
    """Exploit execution outcomes"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    TIMEOUT = "timeout"
    DETECTED = "detected"
    ERROR = "error"


@dataclass
class ExploitAttempt:
    """Record of a single exploit attempt"""
    attempt_id: str
    mission_id: str
    timestamp: datetime
    
    # Context
    target: str
    vulnerability_type: str
    cve_id: Optional[str]
    
    # Exploit details
    exploit_code: str
    obfuscation_techniques: List[str]
    language: str
    
    # Execution
    outcome: OutcomeType
    execution_time: float  # seconds
    error_message: Optional[str] = None
    
    # Rewards
    reward: float = 0.0
    
    # Metadata
    agent_strategy: Optional[str] = None
    llm_model_used: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExploitAttempt':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['outcome'] = OutcomeType(data['outcome'])
        return cls(**data)


class RewardFunction:
    """Calculate rewards for reinforcement learning"""
    
    # Reward values
    REWARDS = {
        OutcomeType.SUCCESS: 1.0,
        OutcomeType.PARTIAL_SUCCESS: 0.5,
        OutcomeType.FAILURE: -0.5,
        OutcomeType.TIMEOUT: -0.3,
        OutcomeType.DETECTED: -1.0,  # Worst outcome - got caught
        OutcomeType.ERROR: -0.2,
    }
    
    # Bonus/penalty modifiers
    SPEED_BONUS = 0.2  # Fast execution
    STEALTH_BONUS = 0.3  # No detection
    COMPLEXITY_PENALTY = 0.1  # Overly complex code
    
    @classmethod
    def calculate(
        cls,
        outcome: OutcomeType,
        execution_time: float,
        code_length: int,
        was_detected: bool = False
    ) -> float:
        """
        Calculate reward for an exploit attempt
        
        Args:
            outcome: Execution outcome
            execution_time: Time taken (seconds)
            code_length: Lines of code
            was_detected: Whether IDS/WAF detected it
        
        Returns:
            Reward value (-1.0 to 1.5)
        """
        # Base reward
        reward = cls.REWARDS.get(outcome, 0.0)
        
        # Speed bonus (< 5 seconds)
        if execution_time < 5.0 and outcome == OutcomeType.SUCCESS:
            reward += cls.SPEED_BONUS
        
        # Stealth bonus
        if not was_detected and outcome == OutcomeType.SUCCESS:
            reward += cls.STEALTH_BONUS
        
        # Complexity penalty (> 100 lines)
        if code_length > 100:
            reward -= cls.COMPLEXITY_PENALTY
        
        return max(-1.0, min(1.5, reward))  # Clamp to [-1.0, 1.5]


class ExperienceReplayBuffer:
    """Store and retrieve past exploit attempts"""
    
    def __init__(self, redis_client: redis.Redis, max_size: int = 10000):
        self.redis = redis_client
        self.max_size = max_size
        self.buffer_key = "ares:experience_buffer"
    
    async def add(self, attempt: ExploitAttempt):
        """Add attempt to buffer"""
        # Serialize
        data = json.dumps(attempt.to_dict())
        
        # Add to Redis list
        await self.redis.lpush(self.buffer_key, data)
        
        # Trim to max size
        await self.redis.ltrim(self.buffer_key, 0, self.max_size - 1)
        
        logger.info(f"Added attempt {attempt.attempt_id} to experience buffer")
    
    async def get_recent(self, n: int = 100) -> List[ExploitAttempt]:
        """Get N most recent attempts"""
        data_list = await self.redis.lrange(self.buffer_key, 0, n - 1)
        
        attempts = []
        for data in data_list:
            try:
                attempt_dict = json.loads(data)
                attempts.append(ExploitAttempt.from_dict(attempt_dict))
            except Exception as e:
                logger.error(f"Failed to parse attempt: {e}")
        
        return attempts
    
    async def get_by_vulnerability(self, vuln_type: str, n: int = 50) -> List[ExploitAttempt]:
        """Get attempts for specific vulnerability type"""
        all_attempts = await self.get_recent(n * 2)  # Get more to filter
        
        filtered = [
            a for a in all_attempts
            if a.vulnerability_type == vuln_type
        ]
        
        return filtered[:n]
    
    async def get_successful(self, n: int = 50) -> List[ExploitAttempt]:
        """Get successful attempts"""
        all_attempts = await self.get_recent(n * 2)
        
        successful = [
            a for a in all_attempts
            if a.outcome == OutcomeType.SUCCESS
        ]
        
        return successful[:n]


class PerformanceAnalyzer:
    """Analyze patterns in exploit attempts"""
    
    def __init__(self, experience_buffer: ExperienceReplayBuffer):
        self.buffer = experience_buffer
    
    async def analyze_success_rate(
        self,
        vulnerability_type: Optional[str] = None,
        time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """Calculate success rate"""
        attempts = await self.buffer.get_recent(1000)
        
        # Filter by vulnerability type
        if vulnerability_type:
            attempts = [a for a in attempts if a.vulnerability_type == vulnerability_type]
        
        # Filter by time window
        cutoff = datetime.now().timestamp() - (time_window_hours * 3600)
        attempts = [a for a in attempts if a.timestamp.timestamp() > cutoff]
        
        if not attempts:
            return {"success_rate": 0.0, "total_attempts": 0}
        
        # Calculate metrics
        total = len(attempts)
        successful = sum(1 for a in attempts if a.outcome == OutcomeType.SUCCESS)
        detected = sum(1 for a in attempts if a.outcome == OutcomeType.DETECTED)
        
        avg_reward = statistics.mean(a.reward for a in attempts)
        avg_time = statistics.mean(a.execution_time for a in attempts)
        
        return {
            "success_rate": successful / total,
            "detection_rate": detected / total,
            "total_attempts": total,
            "avg_reward": avg_reward,
            "avg_execution_time": avg_time,
            "vulnerability_type": vulnerability_type or "all"
        }
    
    async def identify_failure_patterns(self) -> Dict[str, Any]:
        """Identify common failure patterns"""
        attempts = await self.buffer.get_recent(500)
        
        failures = [a for a in attempts if a.outcome in [OutcomeType.FAILURE, OutcomeType.ERROR]]
        
        if not failures:
            return {"patterns": []}
        
        # Group by error message
        error_counts = {}
        for attempt in failures:
            error = attempt.error_message or "Unknown error"
            error_counts[error] = error_counts.get(error, 0) + 1
        
        # Sort by frequency
        patterns = sorted(
            [{"error": k, "count": v} for k, v in error_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        
        return {
            "total_failures": len(failures),
            "unique_errors": len(error_counts),
            "top_patterns": patterns[:10]
        }
    
    async def get_best_strategies(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """Identify most successful strategies"""
        successful = await self.buffer.get_successful(100)
        
        # Group by strategy
        strategy_rewards = {}
        strategy_counts = {}
        
        for attempt in successful:
            strategy = attempt.agent_strategy or "unknown"
            
            if strategy not in strategy_rewards:
                strategy_rewards[strategy] = []
                strategy_counts[strategy] = 0
            
            strategy_rewards[strategy].append(attempt.reward)
            strategy_counts[strategy] += 1
        
        # Calculate average reward per strategy
        strategies = []
        for strategy, rewards in strategy_rewards.items():
            strategies.append({
                "strategy": strategy,
                "avg_reward": statistics.mean(rewards),
                "success_count": strategy_counts[strategy],
                "max_reward": max(rewards)
            })
        
        # Sort by average reward
        strategies.sort(key=lambda x: x["avg_reward"], reverse=True)
        
        return strategies[:top_n]


class AdaptiveLLMPromptOptimizer:
    """Optimize LLM prompts based on feedback"""
    
    def __init__(self, performance_analyzer: PerformanceAnalyzer):
        self.analyzer = performance_analyzer
        self.base_prompts = {}
    
    async def optimize_prompt(
        self,
        agent_role: str,
        vulnerability_type: str
    ) -> str:
        """
        Generate optimized prompt based on past performance
        
        Args:
            agent_role: Which agent (orchestrator, planner, etc.)
            vulnerability_type: Type of vulnerability
        
        Returns:
            Optimized prompt string
        """
        # Analyze performance for this vulnerability type
        stats = await self.analyzer.analyze_success_rate(vulnerability_type)
        
        # Get best strategies
        best_strategies = await self.analyzer.get_best_strategies()
        
        # Get failure patterns
        failures = await self.analyzer.identify_failure_patterns()
        
        # Build adaptive prompt
        prompt_additions = []
        
        # Low success rate - add caution
        if stats["success_rate"] < 0.3:
            prompt_additions.append(
                f"IMPORTANT: Success rate for {vulnerability_type} is low ({stats['success_rate']:.1%}). "
                "Be extra careful with payload generation and validation."
            )
        
        # High detection rate - emphasize stealth
        if stats["detection_rate"] > 0.2:
            prompt_additions.append(
                f"WARNING: Detection rate is high ({stats['detection_rate']:.1%}). "
                "Prioritize stealth and obfuscation techniques."
            )
        
        # Add successful strategies
        if best_strategies:
            strategy_text = ", ".join([s["strategy"] for s in best_strategies[:3]])
            prompt_additions.append(
                f"Previously successful strategies: {strategy_text}"
            )
        
        # Add common failure warnings
        if failures["top_patterns"]:
            top_error = failures["top_patterns"][0]["error"]
            prompt_additions.append(
                f"Common failure: '{top_error}'. Avoid this pattern."
            )
        
        # Combine
        adaptive_prompt = "\n\n".join(prompt_additions)
        
        logger.info(f"Generated adaptive prompt for {agent_role} / {vulnerability_type}")
        return adaptive_prompt


class ReinforcementLearningLoop:
    """Main RL loop orchestrator"""
    
    def __init__(self, redis_url: str):
        self.redis_client = None
        self.redis_url = redis_url
        
        self.reward_function = RewardFunction()
        self.experience_buffer = None
        self.performance_analyzer = None
        self.prompt_optimizer = None
    
    async def initialize(self):
        """Initialize async components"""
        self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)
        
        self.experience_buffer = ExperienceReplayBuffer(self.redis_client)
        self.performance_analyzer = PerformanceAnalyzer(self.experience_buffer)
        self.prompt_optimizer = AdaptiveLLMPromptOptimizer(self.performance_analyzer)
        
        logger.info("Reinforcement Learning Loop initialized")
    
    async def record_attempt(
        self,
        attempt: ExploitAttempt,
        was_detected: bool = False
    ):
        """Record exploit attempt and calculate reward"""
        # Calculate reward
        code_lines = len(attempt.exploit_code.split('\n'))
        
        attempt.reward = self.reward_function.calculate(
            outcome=attempt.outcome,
            execution_time=attempt.execution_time,
            code_length=code_lines,
            was_detected=was_detected
        )
        
        # Store in buffer
        await self.experience_buffer.add(attempt)
        
        logger.info(
            f"Recorded attempt {attempt.attempt_id}: "
            f"{attempt.outcome} (reward: {attempt.reward:.2f})"
        )
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        overall_stats = await self.performance_analyzer.analyze_success_rate()
        best_strategies = await self.performance_analyzer.get_best_strategies()
        failure_patterns = await self.performance_analyzer.identify_failure_patterns()
        
        return {
            "overall_performance": overall_stats,
            "best_strategies": best_strategies,
            "failure_analysis": failure_patterns,
            "generated_at": datetime.now().isoformat()
        }
    
    async def close(self):
        """Cleanup"""
        if self.redis_client:
            await self.redis_client.close()


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Initialize
        rl_loop = ReinforcementLearningLoop(
            redis_url="redis://:insecure_dev_password@localhost:6379/0"
        )
        await rl_loop.initialize()
        
        # Simulate some attempts
        for i in range(10):
            attempt = ExploitAttempt(
                attempt_id=f"test-{i}",
                mission_id="mission-001",
                timestamp=datetime.now(),
                target="192.168.1.10",
                vulnerability_type="RCE",
                cve_id="CVE-2021-44228",
                exploit_code="import os; os.system('whoami')",
                obfuscation_techniques=["base64"],
                language="python",
                outcome=OutcomeType.SUCCESS if i % 3 == 0 else OutcomeType.FAILURE,
                execution_time=2.5,
                agent_strategy="direct_execution"
            )
            
            await rl_loop.record_attempt(attempt)
        
        # Get report
        report = await rl_loop.get_performance_report()
        
        print("\n=== Performance Report ===")
        print(json.dumps(report, indent=2))
        
        # Get optimized prompt
        optimized = await rl_loop.prompt_optimizer.optimize_prompt(
            agent_role="planner",
            vulnerability_type="RCE"
        )
        
        print("\n=== Optimized Prompt ===")
        print(optimized)
        
        await rl_loop.close()
    
    asyncio.run(main())
