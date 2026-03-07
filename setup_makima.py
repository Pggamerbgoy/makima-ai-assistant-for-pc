import os
import subprocess
import sys
import shutil
import urllib.request
import time

def check_command(cmd):
    """Check if a command exists in the system PATH."""
    return shutil.which(cmd) is not None

def run_command(cmd, shell=True):
    """Run a system command and return its output."""
    try:
        result = subprocess.run(cmd, shell=shell, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return None

def install_ollama():
    """Download and install Ollama silently for Windows."""
    print("--- Ollama not found. Starting automatic installation... ---")
    setup_url = "https://ollama.com/download/OllamaSetup.exe"
    setup_path = os.path.join(os.getcwd(), "OllamaSetup.exe")
    
    try:
        print(f"Downloading Ollama installer from {setup_url}...")
        urllib.request.urlretrieve(setup_url, setup_path)
        
        print("Running installer silently... (This may take a minute)")
        # Flags found during research: /SP- /VERYSILENT /NORESTART
        subprocess.run([setup_path, "/SP-", "/VERYSILENT", "/NORESTART"], check=True)
        
        print("Ollama installed successfully! Waiting for service to start...")
        time.sleep(10) # Give it time to initialize
        
        # Cleanup
        if os.path.exists(setup_path):
            os.remove(setup_path)
            
        print("Pulling default model (llama3.2)...")
        subprocess.run(["ollama", "pull", "llama3.2"], shell=True)
        
    except Exception as e:
        print(f"Error during Ollama installation: {e}")
        print("Please install it manually from https://ollama.ai")

def setup_environment():
    """Setup Python dependencies and .env file."""
    print("--- Setting up Python environment... ---")
    
    # 1. Update pip
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    
    # 2. Install requirements
    if os.path.exists("requirements.txt"):
        print("Installing dependencies from requirements.txt...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        except subprocess.CalledProcessError:
            print("Warning: pip install failed. Attempting to install pipwin for PyAudio if on Windows.")
            if os.name == 'nt':
                subprocess.run([sys.executable, "-m", "pip", "install", "pipwin"], check=True)
                subprocess.run([sys.executable, "-m", "pipwin", "install", "pyaudio"], check=True)
                # Retry requirements
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    else:
        print("requirements.txt not found. Skipping dependency install.")

    # 3. Handle .env
    if not os.path.exists(".env"):
        print("Creating default .env file...")
        if os.path.exists(".env.example"):
            shutil.copy(".env.example", ".env")
        else:
            with open(".env", "w") as f:
                f.write("# Makima Configuration\nGEMINI_API_KEY=\nUSER_NAME=User\nMAKIMA_WAKE_WORD=hey makima\n")
        print(".env created. Remember to add your API keys!")

def main():
    print("========================================")
    print("   🌸 Makima AI - Auto Setup Utility 🌸")
    print("========================================\n")

    # Step 1: Check/Install Ollama (Windows only for now)
    if os.name == 'nt':
        if not check_command("ollama"):
            install_ollama()
        else:
            print("✅ Ollama is already installed.")
    else:
        print("ℹ️ Auto-install for Ollama is currently optimized for Windows.")
        if not check_command("ollama"):
            print("Please install Ollama manually for your OS: https://ollama.ai")

    # Step 2: Setup Python & Dependencies
    setup_environment()

    print("\n======================================== text")
    print("   ✅ Setup Complete! You can now run:")
    print("      python makima_assistant.py")
    print("========================================\n")

if __name__ == "__main__":
    main()
