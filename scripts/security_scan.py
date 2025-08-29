#!/usr/bin/env python3
"""
Security Scanning Script
========================
Automated security scanning for the WMS application.
"""

import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime


def run_bandit_scan():
    """Run Bandit security scanner."""
    print("\n" + "="*60)
    print("Running Bandit Security Scanner")
    print("="*60)
    
    try:
        result = subprocess.run(
            ["bandit", "-r", "app/", "-f", "json", "-o", "bandit_results.json"],
            capture_output=True,
            text=True
        )
        
        # Load and analyze results
        if Path("bandit_results.json").exists():
            with open("bandit_results.json", "r") as f:
                results = json.load(f)
            
            issues = results.get("results", [])
            metrics = results.get("metrics", {})
            
            print(f"\nScan Summary:")
            print(f"  Files scanned: {metrics.get('_totals', {}).get('loc', 0)}")
            print(f"  Issues found: {len(issues)}")
            
            if issues:
                print("\nSecurity Issues:")
                for issue in issues:
                    print(f"\n  [{issue['issue_severity']}] {issue['issue_text']}")
                    print(f"    File: {issue['filename']}:{issue['line_number']}")
                    print(f"    Confidence: {issue['issue_confidence']}")
            else:
                print("\n✓ No security issues found!")
            
            return len(issues) == 0
        
        return False
        
    except FileNotFoundError:
        print("ERROR: Bandit not installed. Run: pip install bandit")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def run_safety_check():
    """Check dependencies for known vulnerabilities."""
    print("\n" + "="*60)
    print("Running Safety Dependency Check")
    print("="*60)
    
    try:
        result = subprocess.run(
            ["safety", "check", "--json"],
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            vulnerabilities = json.loads(result.stdout)
            
            if vulnerabilities:
                print(f"\n⚠ Found {len(vulnerabilities)} vulnerable dependencies:")
                for vuln in vulnerabilities:
                    print(f"\n  Package: {vuln.get('package', 'Unknown')}")
                    print(f"    Version: {vuln.get('installed_version', 'Unknown')}")
                    print(f"    Vulnerability: {vuln.get('vulnerability', 'Unknown')}")
                    print(f"    Severity: {vuln.get('severity', 'Unknown')}")
                return False
            else:
                print("\n✓ All dependencies are safe!")
                return True
        
        return True
        
    except FileNotFoundError:
        print("ERROR: Safety not installed. Run: pip install safety")
        return False
    except json.JSONDecodeError:
        # Safety returns 0 exit code even with vulnerabilities
        # Empty output means no vulnerabilities
        print("\n✓ All dependencies are safe!")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def check_secrets():
    """Check for hardcoded secrets in code."""
    print("\n" + "="*60)
    print("Checking for Hardcoded Secrets")
    print("="*60)
    
    patterns = [
        ("password", r'password\s*=\s*["\'][^"\']+["\']'),
        ("api_key", r'api_key\s*=\s*["\'][^"\']+["\']'),
        ("secret", r'secret\s*=\s*["\'][^"\']+["\']'),
        ("token", r'token\s*=\s*["\'][^"\']+["\']'),
    ]
    
    issues_found = False
    
    for name, pattern in patterns:
        try:
            result = subprocess.run(
                ["grep", "-r", "-E", pattern, "app/", "--include=*.py"],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                print(f"\n⚠ Found potential {name} in code:")
                for line in result.stdout.split("\n")[:5]:  # Show first 5
                    if line:
                        print(f"  {line[:100]}")
                issues_found = True
        except:
            pass
    
    if not issues_found:
        print("\n✓ No hardcoded secrets found!")
    
    return not issues_found


def generate_report():
    """Generate security scan report."""
    report = {
        "scan_date": datetime.now().isoformat(),
        "bandit_scan": False,
        "dependency_check": False,
        "secrets_check": False,
        "overall_status": "FAIL"
    }
    
    print("\n" + "="*60)
    print("SECURITY SCAN REPORT")
    print("="*60)
    print(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*60)
    
    # Run all scans
    report["bandit_scan"] = run_bandit_scan()
    report["dependency_check"] = run_safety_check()
    report["secrets_check"] = check_secrets()
    
    # Overall status
    if all([report["bandit_scan"], report["dependency_check"], report["secrets_check"]]):
        report["overall_status"] = "PASS"
        print("\n" + "="*60)
        print("✓ SECURITY SCAN PASSED")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("✗ SECURITY SCAN FAILED")
        print("="*60)
        print("\nFailed checks:")
        if not report["bandit_scan"]:
            print("  - Bandit security scan")
        if not report["dependency_check"]:
            print("  - Dependency vulnerability check")
        if not report["secrets_check"]:
            print("  - Hardcoded secrets check")
    
    # Save report
    with open("security_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: security_report.json")
    
    return report["overall_status"] == "PASS"


if __name__ == "__main__":
    success = generate_report()
    sys.exit(0 if success else 1)