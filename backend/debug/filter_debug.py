
import subprocess
import sys

def main():
    cmd = [sys.executable, "-u", "tests/test_simulation_scenarios.py"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    print("Running test and filtering for DEBUG...")
    
    for line in process.stdout:
        if "DEBUG" in line or "CORE PLAN" in line or "Car 5 Path" in line or "Car 5 Intended" in line:
            print(line, end='')
        
        # Also print progress occasionally to know it's running
        if "PROGRESS" in line:
            print(line, end='')

    process.wait()

if __name__ == "__main__":
    main()
