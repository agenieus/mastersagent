from config import settings
from sentence_transformers import SentenceTransformer
from transformers import pipeline

print("Loading embedding model...")
model = SentenceTransformer(settings.embedding_model)
print("Embedding model loaded.")

print("Loading NLI model...")
pipe = pipeline(
    "text-classification",
    model=settings.nli_model,
    top_k=None,
    device=-1
)
print("NLI model loaded.")
print("All models successfully cached!")
