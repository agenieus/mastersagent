from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Core ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:password@127.0.0.1:5432/aiagent"
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    memory_window: int = 20  # last N messages to include as context

    # ── IMDCRA — Vector Store ─────────────────────────────────────────────
    chroma_persist_dir: str = "./chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"          # ~80 MB

    # ── IMDCRA — NLI Contradiction Resolution ────────────────────────────
    nli_model: str = "cross-encoder/nli-distilroberta-base"  # Valid HF model
    nli_top_k: int = 10               # candidate memories checked per new fact
    nli_contradiction_threshold: float = 0.75  # probability to trigger supersession


    # ── IMDCRA — Decay Engine ─────────────────────────────────────────────
    decay_lambda: float = 0.02        # exponential decay rate (half-life ~35 days)
    decay_weight_recency: float = 0.4
    decay_weight_frequency: float = 0.3
    decay_weight_importance: float = 0.3
    decay_threshold: float = 0.20     # memories below this score are archived

    # ── IMDCRA — Retrieval ────────────────────────────────────────────────
    retrieval_top_k: int = 5          # memories injected into LLM context per turn

    class Config:
        env_file = ".env"


settings = Settings()
