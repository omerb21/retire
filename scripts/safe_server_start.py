#!/usr/bin/env python3
"""
Safe Server Start Script - Ensures clean server startup
Kills any existing Python processes on port 8005 before starting
"""
import subprocess
import sys
import time
import os
import signal

def kill_port_processes(port=8005):
    """Kill all processes listening on the specified port"""
    print(f"🔍 Checking for processes on port {port}...")
    
    try:
        # Get all processes listening on port 8005
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        pids_to_kill = []
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids_to_kill.append(int(pid))
        
        if pids_to_kill:
            print(f"⚠️  Found {len(pids_to_kill)} process(es) on port {port}: {pids_to_kill}")
            
            for pid in pids_to_kill:
                try:
                    print(f"  🗑️  Killing PID {pid}...")
                    subprocess.run(
                        ['taskkill', '/PID', str(pid), '/F', '/T'],
                        timeout=5
                    )
                    print(f"  ✅ Killed PID {pid}")
                except Exception as e:
                    print(f"  ⚠️  Failed to kill PID {pid}: {e}")
            
            # Wait for ports to be released
            print("⏳ Waiting for port to be released...")
            time.sleep(3)
            
            # Verify port is free
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            still_listening = False
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    still_listening = True
                    break
            
            if still_listening:
                print(f"❌ Port {port} is still in use! Retrying...")
                time.sleep(2)
                return kill_port_processes(port)
            else:
                print(f"✅ Port {port} is now free!")
        else:
            print(f"✅ Port {port} is already free")
            
    except Exception as e:
        print(f"⚠️  Error checking port: {e}")

def start_server():
    """Start the Uvicorn server"""
    print("\n🚀 Starting Uvicorn server on port 8005...")
    print("=" * 60)
    
    try:
        subprocess.run(
            [
                sys.executable, '-m', 'uvicorn',
                'app.main:app',
                '--reload',
                '--host', '0.0.0.0',
                '--port', '8005'
            ],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    except KeyboardInterrupt:
        print("\n\n⏹️  Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    print("=" * 60)
    print("🛡️  SAFE SERVER START SCRIPT")
    print("=" * 60)
    
    # Kill any existing processes on port 8005
    kill_port_processes(8005)
    
    # Start the server
    start_server()
