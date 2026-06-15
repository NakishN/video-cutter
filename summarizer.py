from pathlib import Path
from typing import Optional
from config import GEN_API_KEY, GENAPI_NETWORK_ID, SUMMARY_MODEL_PATH, cfg
from jobs import Job
from genapi_client import summarize as genapi_summarize

_gemma_tokenizer = None
_gemma_model = None

GENAPI_MODELS: dict[str, tuple[str, str]] = {
    "genapi-gpt-4-1": ("GPT-4.1", "gpt-4-1"),
    "genapi-gemini": ("Gemini Flash-Lite", "gemini-2-5-flash-lite"),
}
GENAPI_LEGACY_ID = "genapi"

def _resolve_genapi_network(backend: str) -> Optional[str]:
    if backend in GENAPI_MODELS:
        return GENAPI_MODELS[backend][1]
    if backend == GENAPI_LEGACY_ID:
        return GENAPI_NETWORK_ID
    return None

def list_summary_backends() -> list[dict]:
    backends = [
        {"id": "none", "label": "Только транскрипция (без резюме)"},
    ]
    if GEN_API_KEY:
        for backend_id, (label, _network) in GENAPI_MODELS.items():
            backends.append({"id": backend_id, "label": f"Облако: {label} (GenAPI)"})
    return backends

def _default_summary_backend() -> str:
    if not GEN_API_KEY:
        return "none"
    for backend_id, (_label, network) in GENAPI_MODELS.items():
        if network == GENAPI_NETWORK_ID:
            return backend_id
    return next(iter(GENAPI_MODELS))

def _load_local_gemma():
    global _gemma_tokenizer, _gemma_model
    if _gemma_model is not None and _gemma_tokenizer is not None:
        return
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    repo = SUMMARY_MODEL_PATH if SUMMARY_MODEL_PATH.is_dir() else SUMMARY_MODEL_PATH.parent
    _gemma_tokenizer = AutoTokenizer.from_pretrained(
        str(repo), trust_remote_code=True, use_fast=True,
    )
    _gemma_model = AutoModelForCausalLM.from_pretrained(
        str(repo),
        device_map="auto",
        dtype=torch.float16,
        trust_remote_code=True,
    )

def run_summary(
    transcript: str,
    backend: str,
    *,
    transcript_srt: str = "",
    job: Optional[Job] = None,
) -> str:
    if backend == "none":
        return ""

    network_id = _resolve_genapi_network(backend)
    if network_id:
        if not GEN_API_KEY:
            raise RuntimeError("GenAPI не настроен. Добавьте GEN_API_KEY в файл .env")
        model_label = GENAPI_MODELS.get(backend, (network_id, network_id))[0]
        if job:
            job.log(
                f"Анализ интересных моментов через {model_label} (GenAPI)…",
                progress=92,
                status="summarizing",
            )
        text = genapi_summarize(
            transcript, GEN_API_KEY, network_id, transcript_srt=transcript_srt,
        )
        if job:
            job.log("Резюме готово", progress=99)
        return text

    if backend == "local":
        if job:
            job.log("Загрузка локальной Gemma…", progress=92, status="summarizing")
        _load_local_gemma()
        if job:
            job.log("Генерация резюме…", progress=95)
        inputs = _gemma_tokenizer(transcript, return_tensors="pt", truncation=True, max_length=2048)
        inputs = {k: v.to(_gemma_model.device) for k, v in inputs.items()}
        output_ids = _gemma_model.generate(**inputs, max_new_tokens=200, do_sample=False)
        return _gemma_tokenizer.decode(output_ids[0], skip_special_tokens=True)

    raise RuntimeError(f"Неизвестный режим резюме: {backend}")
