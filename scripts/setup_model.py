import os
import sys

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    print("❌ Error: 'huggingface_hub' is not installed.")
    print("Please run: pip install huggingface-hub")
    sys.exit(1)

REPO_ID = "microsoft/Phi-3-mini-4k-instruct-gguf"
FILENAME = "Phi-3-mini-4k-instruct-q4.gguf"

# Define target directory: app/writing/models_gguf
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_DIR = os.path.join(PROJECT_ROOT, "app", "writing", "models_gguf")

def main():
    print(f"🚀 Starting model download process...")
    print(f"📦 Repository: {REPO_ID}")
    print(f"📄 File: {FILENAME}")
    print(f"📂 Target Directory: {TARGET_DIR}")
    print("-" * 50)
    
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    try:
        print("⏳ Downloading (this may take a while depending on your internet connection)...")
        file_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            local_dir=TARGET_DIR,
            local_dir_use_symlinks=False
        )
        print("-" * 50)
        print(f"✅ Success! Model downloaded to: {file_path}")
        print("💡 You can now start the LLM Server using: python app/writing/llm_server.py")
    except Exception as e:
        print("-" * 50)
        print(f"❌ Failed to download model. Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
