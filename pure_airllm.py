#!/usr/bin/env python3
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Make torch optional so tests can run without GPU/torch installed
try:
    import torch
except Exception:
    torch = None

try:
    from airllm import AutoModel
    from airllm.airllm_llama_mlx import AirLLMLlamaMlx
except Exception:
    AutoModel = None
    AirLLMLlamaMlx = None

app = FastAPI()

print("Preparing model (use SKIP_MODEL_LOAD=1 to run in test/dry-run mode)...")

# Support a safe test mode that doesn't download / load the large model.
SKIP_MODEL_LOAD = os.environ.get("SKIP_MODEL_LOAD", "0") in ("1", "true", "True")

class DummyTokenizer:
    def __call__(self, text, return_tensors=None):
        return {"input_ids": text}
    def decode(self, tokens, skip_special_tokens=True):
        return tokens

class DummyModel:
    def __init__(self):
        self.tokenizer = DummyTokenizer()
    def generate(self, input_ids, max_new_tokens=150):
        # Echo back a simple canned response for testing
        prompt = input_ids if isinstance(input_ids, str) else str(input_ids)
        return prompt + "\n\nAssistant: (test-mode response)"

MODEL_ID = os.environ.get("MODEL_ID", "deepreinforce-ai/Ornith-1.0-397B")

def patch_ornith_layer_names():
    if AirLLMLlamaMlx is None:
        return

    def set_layer_names_dict(self):
        self.layer_names_dict = {
            'embed': 'model.language_model.embed_tokens',
            'layer_prefix': 'model.language_model.layers',
            'norm': 'model.language_model.norm',
            'lm_head': 'lm_head',
        }

    AirLLMLlamaMlx.set_layer_names_dict = set_layer_names_dict

if SKIP_MODEL_LOAD:
    model = DummyModel()
else:
    if AutoModel is None:
        raise RuntimeError("airllm.AutoModel not available; set SKIP_MODEL_LOAD=1 for testing or install airllm")
    if 'Ornith-1.0-397B' in MODEL_ID.lower() or 'ornith' in MODEL_ID.lower():
        patch_ornith_layer_names()

    use_cuda = torch is not None and torch.cuda.is_available()
    use_mps = torch is not None and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
    compression_setting = None
    if use_cuda:
        device_setting = "cuda:0"
    elif use_mps:
        device_setting = "mps"
    else:
        device_setting = "cpu"

    print(f"Loading {MODEL_ID} layer-by-layer directly onto your SSD on device={device_setting} using full-precision weights...")

    model = AutoModel.from_pretrained(
        MODEL_ID,
        device=device_setting,
        compression=compression_setting,
        delete_original=True,
        show_memory_util=True,
    )

@app.post("/v1/messages")
async def anthropic_messages_endpoint(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    
    # Reassemble conversation history into a unified text prompt block
    prompt = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        prompt += f"\n\nHuman: {content}" if role == "user" else f"\n\nAssistant: {content}"
    prompt += "\n\nAssistant: "

    # Execute generation (works in both real and dummy/test modes)
    input_tokens = model.tokenizer(prompt, return_tensors="pt")
    input_ids = input_tokens['input_ids']
    # If using torch tensors and CUDA is available, move to CUDA. Otherwise pass through.
    if hasattr(input_ids, 'cuda') and torch is not None:
        input_ids_to_use = input_ids.cuda()
    else:
        input_ids_to_use = input_ids

    output_tokens = model.generate(
        input_ids_to_use,
        max_new_tokens=150
    )
    generated_text = model.tokenizer.decode(output_tokens, skip_special_tokens=True)
    clean_response = generated_text.replace(prompt, "").strip()

    # Reply using Anthropic's official schema format required by Claude Code
    return JSONResponse({
        "id": "msg_local_airllm_generation",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": clean_response}],
        "model": "ornith-1.0-397b",
        "stop_reason": "end_turn"
    })

if __name__ == "__main__":
    # Start the backend server on port 9000
    uvicorn.run(app, host="127.0.0.1", port=9000)
