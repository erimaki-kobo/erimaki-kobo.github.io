# Bodies copied from each engine's source (file and version in the "src" field).
import json
L, P, M = 4096, 5000, 1000
def vnest(msg, param=None, value=None, code=400, typ="BadRequestError"):
    if param: msg += f" (parameter={param}, value={value})"
    return {"error": {"message": msg, "type": typ, "param": param, "code": code}}
cases = [
 {"id": "vllm_v0.32+_prompt_over", "src": "vllm v0.34.0 vllm/renderers/params.py _token_len_check", "status": 400,
  "body": vnest(f"This model's maximum context length is {L} tokens. However, your prompt contains {P} input tokens, which exceeds this limit even without any output tokens. Please reduce the length of the input prompt.", "input_tokens", P)},
 {"id": "vllm_v0.32+_prompt_equals_limit", "src": "vllm v0.34.0 sampling_params.py (max_tokens clamped to 0 by get_max_tokens)", "status": 400,
  "body": vnest("max_tokens must be at least 1, got 0.", "max_tokens", 0)},
 {"id": "vllm_v0.32+_max_tokens_over_limit", "src": "vllm v0.34.0 vllm/renderers/params.py __post_init__", "status": 400,
  "body": vnest(f"max_tokens={L+1} cannot be greater than max_model_len={L}. Please request fewer output tokens.", "max_tokens", L+1)},
 {"id": "vllm_v0.10-v0.31_prompt_plus_max_tokens", "src": "vllm v0.17.1 entrypoints/openai/engine/serving.py", "status": 400,
  "body": vnest(f"'max_tokens' or 'max_completion_tokens' is too large: {M}. This model's maximum context length is {L} tokens and your request has {L-500} input tokens ({M} > {L} - {L-500}).", "max_tokens", M)},
 {"id": "vllm_v0.10-v0.31_prompt_over", "src": "vllm v0.17.1 entrypoints/openai/engine/serving.py", "status": 400,
  "body": vnest(f"This model's maximum context length is {L} tokens. However, your request has {P} input tokens. Please reduce the length of the input messages.", "input_tokens", P)},
 {"id": "vllm_v0.9_and_older", "src": "vllm v0.9.2 entrypoints/openai/serving_engine.py (flat ErrorResponse)", "status": 400,
  "body": {"object": "error", "message": f"This model's maximum context length is {L} tokens. However, you requested {P+M} tokens ({P} in the messages, {M} in the completion). Please reduce the length of the messages or completion.", "type": "BadRequestError", "param": None, "code": 400}},
 {"id": "sglang_prompt_over", "src": "sglang tokenizer_manager.py _validate_input_ids_in_context_length; serving_base.py create_error_response", "status": 400,
  "body": {"object": "error", "message": f"The input ({P} tokens) is longer than the model's context length ({L} tokens).", "type": "BadRequestError", "param": None, "code": 400}},
 {"id": "sglang_prompt_plus_max_tokens", "src": "sglang tokenizer_manager.py (v0.4.1.post7+)", "status": 400,
  "body": {"object": "error", "message": f"Requested token count exceeds the model's maximum context length of {L} tokens. You requested a total of {L-500+M} tokens: {L-500} tokens from the input messages and {M} tokens for the completion. Please reduce the number of tokens in the input messages or the completion to fit within the limit.", "type": "BadRequestError", "param": None, "code": 400}},
 {"id": "sglang_v0.5.9_and_older_stream", "src": "sglang v0.5.9 serving_chat.py _generate_chat_stream (HTTP 200, error inside SSE)",
  "sse": [{"object": "error", "message": f"The input ({P} tokens) is longer than the model's context length ({L} tokens).", "type": "BadRequestError", "param": None, "code": 400}, "[DONE]"]},
 {"id": "llamacpp_b7481+", "src": "llama.cpp tools/server/server-context.cpp + server-task.cpp", "status": 400,
  "body": {"error": {"code": 400, "message": f"request ({P} tokens) exceeds the available context size ({L} tokens), try increasing it", "type": "exceed_context_size_error", "n_prompt_tokens": P, "n_ctx": L}}},
 {"id": "llamacpp_b6380-b7480", "src": "llama.cpp b6724 tools/server/server.cpp", "status": 400,
  "body": {"error": {"code": 400, "message": "the request exceeds the available context size. try increasing the context size or enable context shift", "type": "exceed_context_size_error", "n_prompt_tokens": P, "n_ctx": L}}},
 {"id": "llamacpp_no_split_model", "src": "llama.cpp server-context.cpp (models that cannot split the prompt)", "status": 400,
  "body": {"error": {"code": 400, "message": f"input ({P} tokens) is larger than the max context size ({L} tokens). skipping", "type": "exceed_context_size_error", "n_prompt_tokens": P, "n_ctx": L}}},
 {"id": "ollama_v1_shift_off", "src": "ollama llm/llama_server.go promptTooLongMessage; openai/openai.go NewError", "status": 400,
  "body": {"error": {"message": "the prompt is longer than the context length currently available to the model; shorten the prompt, adjust the context length in settings, or use a model with a longer context length", "type": "invalid_request_error", "param": None, "code": None}}},
 {"id": "ollama_native_shift_off", "src": "ollama /api/chat", "path": "/api/chat", "status": 400,
  "body": {"error": "the prompt is longer than the context length currently available to the model; shorten the prompt, adjust the context length in settings, or use a model with a longer context length"}},
 {"id": "tgi", "src": "text-generation-inference router/src/validation.rs, server.rs (422)", "status": 422,
  "body": {"error": f"Input validation error: `inputs` tokens + `max_new_tokens` must be <= {L}. Given: {L-500} `inputs` tokens and {M} `max_new_tokens`", "error_type": "validation"}},
 {"id": "dynamo_frontend", "src": "dynamo lib/llm/src/http/service/error.rs openai_context_length_message", "status": 400,
  "body": {"error": {"message": f"This model's maximum context length is {L} tokens. However, your messages resulted in {P} tokens. Please reduce the length of the messages.", "type": "invalid_request_error", "param": None, "code": 400}}},
 {"id": "generic_500_overflow", "src": "any engine that maps the overflow to 500 (e.g. Dynamo <=1.6.1 with TensorRT-LLM, PR #16193)", "status": 500,
  "body": {"error": {"message": f"prompt length {P} exceeds max_num_tokens {L}", "type": "internal_server_error", "param": None, "code": 500}}},
]
json.dump(cases, open("cases.json", "w"), indent=1)
print(len(cases))
