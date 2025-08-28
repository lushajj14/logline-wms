#!/usr/bin/env python3
"""
Generate secure API secret key for the application.
Run this script to generate a cryptographically secure secret key.
"""

import secrets
import sys
import os

def generate_secret_key(length=32):
    """Generate a cryptographically secure URL-safe secret key."""
    return secrets.token_urlsafe(length)

def main():
    print("="*60)
    print("API SECRET KEY GENERATOR")
    print("="*60)
    
    # Generate new secret
    secret = generate_secret_key()
    
    print(f"\nGenerated Secret Key:\n{secret}\n")
    print("How to use this secret key:")
    print("-"*40)
    
    # Windows
    print("On Windows (Command Prompt):")
    print(f"  set API_SECRET={secret}")
    print()
    
    print("On Windows (PowerShell):")
    print(f"  $env:API_SECRET=\"{secret}\"")
    print()
    
    # Linux/Mac
    print("On Linux/Mac:")
    print(f"  export API_SECRET={secret}")
    print()
    
    # .env file
    print("Or add to .env file:")
    print(f"  API_SECRET={secret}")
    print()
    
    # Docker
    print("For Docker:")
    print(f"  docker run -e API_SECRET={secret} ...")
    print()
    
    print("="*60)
    print("IMPORTANT: Save this key securely!")
    print("You won't be able to recover it once you close this window.")
    print("="*60)
    
    # Optionally save to .env file
    response = input("\nDo you want to save this to .env file? (y/n): ").lower()
    if response == 'y':
        env_file = os.path.join(os.path.dirname(__file__), '.env')
        
        # Check if .env exists and has API_SECRET
        update_existing = False
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                content = f.read()
                if 'API_SECRET=' in content:
                    response = input(".env file already has API_SECRET. Overwrite? (y/n): ").lower()
                    if response != 'y':
                        print("Skipping .env update.")
                        return
                    update_existing = True
        
        # Update or append to .env
        if update_existing:
            # Read existing content
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            # Update API_SECRET line
            with open(env_file, 'w') as f:
                for line in lines:
                    if line.startswith('API_SECRET='):
                        f.write(f'API_SECRET={secret}\n')
                    else:
                        f.write(line)
        else:
            # Append to .env
            with open(env_file, 'a') as f:
                if os.path.getsize(env_file) > 0:
                    f.write('\n')
                f.write(f'API_SECRET={secret}\n')
        
        print(f"✓ Secret key saved to {env_file}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()