import ollama
from config import settings
from typing import List, Dict, AsyncGenerator, Optional

BASE_SYSTEM_PROMPT = """You are a highly capable AI assistant with expertise across many domains:

• **Software Development & Coding** — Python, JavaScript, TypeScript, SQL, Bash, and more. You write clean, working code with clear explanations.
• **Data Science & Machine Learning** — algorithms, frameworks (PyTorch, TensorFlow, scikit-learn), statistics.
• **General Knowledge & Reasoning** — history, science, mathematics, philosophy, current concepts.
• **Creative Problem Solving** — breaking down complex problems, architecture design, debugging.

Guidelines:
- Always provide accurate, well-reasoned answers.
- For coding questions, include working code examples with comments.
- Format responses using Markdown (headers, bullet points, code blocks) for clarity.
- If you're unsure about something, say so clearly rather than guessing.
- Use the full conversation history to give contextual, coherent responses.
- When remembered facts about the user are provided, use them naturally to personalise your response.
"""


def build_system_prompt(memory_context: Optional[str] = None) -> str:
    """Construct the system prompt, optionally injecting retrieved memory context."""
    if memory_context:
        return BASE_SYSTEM_PROMPT + f"\n\n{memory_context}\n"
    return BASE_SYSTEM_PROMPT


async def stream_response(
    messages: List[Dict[str, str]],
    memory_context: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream a response token-by-token from Ollama, with optional memory context."""
    system_prompt = build_system_prompt(memory_context)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    client = ollama.AsyncClient(host=settings.ollama_host)
    stream = await client.chat(
        model=settings.ollama_model,
        messages=full_messages,
        stream=True,
    )

    async for chunk in stream:
        if chunk.message and chunk.message.content:
            yield chunk.message.content
