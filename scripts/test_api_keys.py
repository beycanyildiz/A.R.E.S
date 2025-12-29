"""
Quick Test - API Keys & LLM Providers

Bu script API keylerini ve LLM modellerini test eder.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Load environment variables
load_dotenv()

def test_env_variables():
    """Test environment variables"""
    console.print("\n[bold cyan]Testing Environment Variables...[/bold cyan]")
    
    required_vars = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "PRIMARY_LLM": os.getenv("PRIMARY_LLM"),
        "SECONDARY_LLM": os.getenv("SECONDARY_LLM"),
    }
    
    table = Table(title="Environment Variables")
    table.add_column("Variable", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Value Preview", style="yellow")
    
    all_ok = True
    for var, value in required_vars.items():
        if value:
            # Show first 20 chars for security
            preview = value[:20] + "..." if len(value) > 20 else value
            table.add_row(var, "✓ SET", preview)
        else:
            table.add_row(var, "✗ MISSING", "Not set")
            all_ok = False
    
    console.print(table)
    return all_ok


def test_llm_providers():
    """Test LLM provider initialization"""
    console.print("\n[bold cyan]Testing LLM Providers...[/bold cyan]")
    
    try:
        from services.cognitive_agents.agent_framework import LLMProvider
        
        provider = LLMProvider()
        
        if not provider.models:
            console.print("[red]✗ No LLM models initialized![/red]")
            return False
        
        console.print(f"[green]✓ Initialized {len(provider.models)} models:[/green]")
        for model_name in provider.models.keys():
            console.print(f"  • {model_name}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Failed to initialize LLM providers: {e}[/red]")
        return False


def test_openai_connection():
    """Test OpenAI API connection"""
    console.print("\n[bold cyan]Testing OpenAI Connection...[/bold cyan]")
    
    try:
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(
            model="gpt-4o-mini",  # Use mini for testing (cheaper)
            temperature=0.7,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        console.print("  Sending test request to OpenAI...")
        response = llm.invoke("Say 'Hello from A.R.E.S!' in one sentence.")
        
        console.print(f"[green]✓ OpenAI Response:[/green]")
        console.print(f"  {response.content}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ OpenAI test failed: {e}[/red]")
        return False


def test_gemini_connection():
    """Test Google Gemini API connection"""
    console.print("\n[bold cyan]Testing Google Gemini Connection...[/bold cyan]")
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",  # Use flash for testing (faster)
            temperature=0.7,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            convert_system_message_to_human=True
        )
        
        console.print("  Sending test request to Gemini...")
        response = llm.invoke("Say 'Hello from A.R.E.S. with Gemini!' in one sentence.")
        
        console.print(f"[green]✓ Gemini Response:[/green]")
        console.print(f"  {response.content}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Gemini test failed: {e}[/red]")
        return False


def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold cyan]A.R.E.S. Quick Test[/bold cyan]\n"
        "Testing API Keys & LLM Providers",
        border_style="cyan"
    ))
    
    results = []
    
    # Test 1: Environment variables
    results.append(("Environment Variables", test_env_variables()))
    
    # Test 2: LLM provider initialization
    results.append(("LLM Provider Init", test_llm_providers()))
    
    # Test 3: OpenAI connection
    results.append(("OpenAI Connection", test_openai_connection()))
    
    # Test 4: Gemini connection
    results.append(("Gemini Connection", test_gemini_connection()))
    
    # Summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]Test Summary[/bold cyan]")
    console.print("="*60)
    
    table = Table()
    table.add_column("Test", style="cyan")
    table.add_column("Result", style="green")
    
    for test_name, passed in results:
        status = "[green]✓ PASSED[/green]" if passed else "[red]✗ FAILED[/red]"
        table.add_row(test_name, status)
    
    console.print(table)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    console.print(f"\n[bold]Results: {passed_count}/{total_count} tests passed[/bold]")
    
    if passed_count == total_count:
        console.print("\n[bold green]🎉 All tests passed! System is ready![/bold green]")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  1. Start infrastructure: docker-compose up -d")
        console.print("  2. Run Phase 1 tests: python scripts/test_integration.py")
        console.print("  3. Run Phase 2 tests: python scripts/test_phase2.py")
    else:
        console.print("\n[bold yellow]⚠ Some tests failed. Check the errors above.[/bold yellow]")


if __name__ == "__main__":
    main()
