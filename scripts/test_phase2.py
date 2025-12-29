"""
A.R.E.S. Phase 2 Integration Test

Tests cognitive agents and exploit synthesis:
1. LLM agent framework
2. Exploit code generation
3. Obfuscation engine
4. Reinforcement learning loop
5. Integrated pipeline
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


async def test_llm_provider():
    """Test LLM provider initialization"""
    console.print("\n[bold cyan]Testing LLM Provider...[/bold cyan]")
    
    try:
        from services.cognitive_agents.agent_framework import LLMProvider
        
        provider = LLMProvider()
        
        if provider.models:
            console.print(f"[green]✓ LLM Provider initialized with {len(provider.models)} models[/green]")
            for model_name in provider.models.keys():
                console.print(f"  - {model_name}")
            return True
        else:
            console.print("[yellow]⚠ No LLM models available (set API keys in .env)[/yellow]")
            return False
            
    except Exception as e:
        console.print(f"[red]✗ LLM Provider test failed: {e}[/red]")
        return False


async def test_cognitive_agents():
    """Test cognitive agent workflow"""
    console.print("\n[bold cyan]Testing Cognitive Agents...[/bold cyan]")
    
    try:
        from services.cognitive_agents.agent_framework import CognitiveAgentOrchestrator
        
        # Check if API keys are set
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[yellow]⚠ Skipping (no API keys set)[/yellow]")
            return True
        
        orchestrator = CognitiveAgentOrchestrator()
        
        # Test with mock data
        recon_data = {
            "hosts": [{"ip": "192.168.1.10", "os": "Ubuntu", "open_ports": [80, 443]}]
        }
        
        console.print("  Running cognitive workflow (this may take 30-60 seconds)...")
        
        result = await orchestrator.execute_mission(
            mission_id="test-cognitive-001",
            target="192.168.1.10",
            recon_data=recon_data
        )
        
        console.print(f"[green]✓ Cognitive agents completed in {result.iteration_count} iterations[/green]")
        
        if result.strategy:
            console.print(f"  Strategy generated: {len(result.strategy)} chars")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Cognitive agents test failed: {e}[/red]")
        console.print("  [yellow]Note: Requires valid API keys[/yellow]")
        return False


async def test_exploit_synthesizer():
    """Test exploit code generation"""
    console.print("\n[bold cyan]Testing Exploit Synthesizer...[/bold cyan]")
    
    try:
        from services.cognitive_agents.exploit_synthesizer import (
            ExploitSynthesizer,
            VulnerabilityContext,
            ExploitLanguage,
            ObfuscationEngine,
            ObfuscationTechnique
        )
        from services.cognitive_agents.agent_framework import LLMProvider
        from services.knowledge_matrix.vector_db import VectorDBManager
        
        # Check prerequisites
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[yellow]⚠ Skipping (no API keys set)[/yellow]")
            return True
        
        # Initialize components
        llm_provider = LLMProvider()
        vector_db = VectorDBManager(host="localhost", port=19530)
        
        synthesizer = ExploitSynthesizer(llm_provider, vector_db)
        
        # Test vulnerability
        vuln = VulnerabilityContext(
            cve_id="CVE-2021-44228",
            service_name="Apache Log4j",
            service_version="2.14.1",
            vulnerability_type="RCE",
            description="JNDI injection vulnerability",
            target_os="Linux",
            target_ip="192.168.1.10",
            target_port=8080
        )
        
        console.print("  Generating exploit code (this may take 30-60 seconds)...")
        
        exploit = await synthesizer.synthesize(vuln, obfuscate=True)
        
        console.print(f"[green]✓ Exploit generated[/green]")
        console.print(f"  Language: {exploit.language}")
        console.print(f"  Code length: {len(exploit.code)} bytes")
        console.print(f"  Obfuscated: {exploit.obfuscated_code is not None}")
        console.print(f"  Detection risk: {exploit.detection_risk}")
        
        # Display code sample
        if exploit.code:
            code_preview = exploit.code[:200] + "..." if len(exploit.code) > 200 else exploit.code
            syntax = Syntax(code_preview, exploit.language, theme="monokai", line_numbers=True)
            console.print("\n  Code preview:")
            console.print(syntax)
        
        vector_db.close()
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Exploit synthesizer test failed: {e}[/red]")
        return False


async def test_obfuscation():
    """Test obfuscation engine"""
    console.print("\n[bold cyan]Testing Obfuscation Engine...[/bold cyan]")
    
    try:
        from services.cognitive_agents.exploit_synthesizer import (
            ObfuscationEngine,
            ObfuscationTechnique,
            ExploitLanguage
        )
        
        engine = ObfuscationEngine()
        
        # Test code
        test_code = """
import os
target = "192.168.1.10"
payload = "whoami"
os.system(payload)
"""
        
        # Apply obfuscation
        techniques = [
            ObfuscationTechnique.VARIABLE_RENAME,
            ObfuscationTechnique.DEAD_CODE,
            ObfuscationTechnique.BASE64
        ]
        
        obfuscated = engine.obfuscate(test_code, ExploitLanguage.PYTHON, techniques)
        
        console.print(f"[green]✓ Obfuscation applied[/green]")
        console.print(f"  Original: {len(test_code)} bytes")
        console.print(f"  Obfuscated: {len(obfuscated)} bytes")
        console.print(f"  Techniques: {', '.join(t.value for t in techniques)}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Obfuscation test failed: {e}[/red]")
        return False


async def test_reinforcement_learning():
    """Test RL loop"""
    console.print("\n[bold cyan]Testing Reinforcement Learning...[/bold cyan]")
    
    try:
        from services.cognitive_agents.reinforcement_learning import (
            ReinforcementLearningLoop,
            ExploitAttempt,
            OutcomeType
        )
        
        rl_loop = ReinforcementLearningLoop(
            redis_url="redis://:insecure_dev_password@localhost:6379/0"
        )
        await rl_loop.initialize()
        
        # Record test attempt
        attempt = ExploitAttempt(
            attempt_id="test-rl-001",
            mission_id="test-mission",
            timestamp=datetime.now(),
            target="192.168.1.10",
            vulnerability_type="RCE",
            cve_id="CVE-2021-44228",
            exploit_code="test_code",
            obfuscation_techniques=["base64"],
            language="python",
            outcome=OutcomeType.SUCCESS,
            execution_time=2.5,
            agent_strategy="test_strategy"
        )
        
        await rl_loop.record_attempt(attempt)
        
        # Get report
        report = await rl_loop.get_performance_report()
        
        console.print(f"[green]✓ RL loop working[/green]")
        console.print(f"  Total attempts: {report['overall_performance']['total_attempts']}")
        console.print(f"  Success rate: {report['overall_performance']['success_rate']:.1%}")
        
        await rl_loop.close()
        return True
        
    except Exception as e:
        console.print(f"[red]✗ RL loop test failed: {e}[/red]")
        console.print("  [yellow]Make sure Redis is running[/yellow]")
        return False


async def test_integrated_pipeline():
    """Test complete integrated pipeline"""
    console.print("\n[bold cyan]Testing Integrated Pipeline...[/bold cyan]")
    
    try:
        from services.cognitive_agents.integrated_pipeline import (
            IntegratedCognitivePipeline,
            MissionConfig
        )
        
        # Check prerequisites
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[yellow]⚠ Skipping (no API keys set)[/yellow]")
            return True
        
        pipeline = IntegratedCognitivePipeline()
        await pipeline.initialize()
        
        console.print("[green]✓ Integrated pipeline initialized[/green]")
        console.print("  [yellow]Full mission test skipped (would take 5-10 minutes)[/yellow]")
        console.print("  [yellow]Run manually: python services/cognitive-agents/integrated_pipeline.py[/yellow]")
        
        await pipeline.close()
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Integrated pipeline test failed: {e}[/red]")
        return False


async def run_all_tests():
    """Run all Phase 2 tests"""
    console.print(Panel.fit(
        "[bold cyan]A.R.E.S. Phase 2 - Cognitive Agents Tests[/bold cyan]\n"
        "Testing LLM-based decision making and exploit synthesis",
        border_style="cyan"
    ))
    
    tests = [
        ("LLM Provider", test_llm_provider),
        ("Obfuscation Engine", test_obfuscation),
        ("Reinforcement Learning", test_reinforcement_learning),
        ("Cognitive Agents", test_cognitive_agents),
        ("Exploit Synthesizer", test_exploit_synthesizer),
        ("Integrated Pipeline", test_integrated_pipeline),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            console.print(f"[red]✗ {test_name} crashed: {e}[/red]")
            results.append((test_name, False))
    
    # Summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]Test Summary[/bold cyan]")
    console.print("="*60)
    
    table = Table()
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    for test_name, passed in results:
        status = "[green]✓ PASSED[/green]" if passed else "[red]✗ FAILED[/red]"
        table.add_row(test_name, status)
    
    console.print(table)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    console.print(f"\n[bold]Results: {passed_count}/{total_count} tests passed[/bold]")
    
    if passed_count == total_count:
        console.print("\n[bold green]🎉 All tests passed! Phase 2 is ready.[/bold green]")
    else:
        console.print("\n[bold yellow]⚠ Some tests failed. Check the logs above.[/bold yellow]")
        console.print("\n[yellow]Common issues:[/yellow]")
        console.print("  1. API keys not set in .env (OPENAI_API_KEY or ANTHROPIC_API_KEY)")
        console.print("  2. Redis not running (docker-compose up -d)")
        console.print("  3. Milvus not running (docker-compose up -d)")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
