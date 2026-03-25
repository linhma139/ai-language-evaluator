import grpc
from concurrent import futures
import time
import threading
import os
import sys

# Setup resolve paths for core logger
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.logger import logger

import llm_pb2
import llm_pb2_grpc

from llama_cpp import Llama

# New path pointing to the models_gguf directory just created in writing/
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models_gguf", "Phi-3-mini-4k-instruct-q4.gguf")

class LLMServiceServicer(llm_pb2_grpc.LLMServiceServicer):
    def __init__(self):
        if not os.path.exists(MODEL_PATH):
            error_msg = (
                f"\n{'='*60}\n"
                f"🚨 CRITICAL ERROR: Model file not found!\n"
                f"Path checked: {MODEL_PATH}\n\n"
                f"👉 ACTION REQUIRED: Please run the setup script to download the model:\n"
                f"   python scripts/setup_model.py\n"
                f"{'='*60}\n"
            )
            logger.error(error_msg)
            sys.exit(1)
            
        logger.info(f"Loading model from {MODEL_PATH}...")
        self.lock = threading.Lock()
        try:
            # Adjust n_ctx depending on requirements, phi-3-mini-4k supports 4096
            self.llm = Llama(model_path=MODEL_PATH, n_ctx=4096, n_gpu_layers=-1) # Attempt GPU usage, gracefully fallback to CPU
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading model: {e}", exc_info=True)
            raise e

    def Generate(self, request, context):
        logger.info(f"Received Generate request with prompt length: {len(request.prompt)}")
        prompt = request.prompt
        temperature = request.temperature if request.temperature > 0 else 0.2
        max_tokens = request.max_tokens if request.max_tokens > 0 else 1024

        try:
            # If prompt doesn't have system/user mapping, we can just pass it directly or format it. 
            # In writing_service it sends a formatted prompt already.
            with self.lock:
                response = self.llm(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=["<|end|>"]
                )
            
            output_text = response["choices"][0]["text"]
            return llm_pb2.GenerateResponse(text=output_text)
            
        except Exception as e:
            logger.error(f"Error during generation: {e}", exc_info=True)
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return llm_pb2.GenerateResponse()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    llm_pb2_grpc.add_LLMServiceServicer_to_server(LLMServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    logger.info("gRPC LLM Server started on port 50051.")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
