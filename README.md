# IELTS & TOEIC AI Server

This is a professional Microservice backend designed to evaluate **IELTS & TOEIC Speaking and Writing** skills. It uses a combination of Google's Gemini, Google Cloud Speech-to-Text (ASR) for speaking, and a Local LLM (e.g., Phi-3-mini) over a gRPC connection for writing evaluation.

## 🚀 Features

- **Speaking Module:** 
  - Manage speaking sessions with Candidates.
  - Automatically transcribe audio using Google Speech-to-Text (`LINEAR16`, `WEBM_OPUS`).
  - Extract acoustic features via `librosa`.
  - Interact with candidates dynamically via Gemini API based on a system prompt.
- **Writing Module:**
  - High-performance evaluation using a Local LLM via gRPC.
  - Returns detailed sub-scores (Task Achievement, CC, LR, GRA) and text feedback using RegEx formatting.

## 📂 Project Structure

```text
app/
├── api/             # API Routers (speaking.py, writing.py) and Dependency Injection (deps.py)
├── core/            # Configuration (pydantic-settings) and clean Logging system
├── speaking/        # Audio Processing, ASR logic, LLM helpers, and Session management
├── writing/         # Local LLM integration (llm_server.py) and Writing logic
├── main.py          # Entry point for the FastAPI server (Middlewares, routers)
└── models.py        # Pydantic data models for Request/Response validation
```

## 🛠 Prerequisites

Ensure you have the following installed to run this project:
- **Python 3.10 or 3.11** *(Important: Do not use newer versions like 3.12+ on Windows unless you have Visual Studio C++ Build Tools installed, to avoid `llama-cpp-python` compilation errors).*
- **FFmpeg**: Must be installed and added to your system's PATH variable (used for audio fallback preprocessing if needed).
- **Google Cloud Service Account** with Google Cloud Storage and Speech-to-Text APIs enabled.

## ⚙️ Setup Environment

**1. Create a virtual environment & install dependencies:**
```bash
python -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Setup Google Cloud & Environment Variables:**
Place your Google Cloud Service Account JSON key inside the root directory and rename it to `service-account-key.json` (This file is ignored by git).

Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GCS_BUCKET_NAME=your_gcs_bucket_name
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
PORT=8000
```

**3. Download Local LLM (For Writing):**
Instead of downloading manually, we provide a setup script that safely downloads the optimal GGUF model via Hugging Face.
Run the following command in your terminal:
```bash
python scripts/setup_model.py
```
*(This will download `Phi-3-mini-4k-instruct-q4.gguf` into `app/writing/models_gguf/` and display a progress bar).*

## 🚀 Running the Application

This architecture splits the heavy ML inference workload using gRPC. You need to start two separate server processes.

**1. Start the gRPC Local LLM Server:**
This server loads the GGUF model and waits for generation requests.
```bash
python app/writing/llm_server.py
```
*(Runs on localhost:50051)*

**2. Start the FastAPI Server:**
Open a new terminal and run the main entry point:
```bash
python app/main.py
```
*(Runs on http://localhost:8000)*

## 📖 API Documentation & Testing
Once the FastAPI server is running, interactive API documentation is automatically generated:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

You can also test basic speaking functionalities directly by visiting the built-in UI at:
[http://localhost:8000/ui/](http://localhost:8000/ui/)
