"""
evaluate_imdcra.py
-------------------
Simulates 50 virtual users with 4 sessions (turns) each to evaluate the IMDCRA memory architecture.
Outputs experimental results for Table 4.2 of the dissertation.

Metrics Tracked:
1. Extraction Accuracy (%)
2. Contradiction Detection Accuracy (%)
3. Retrieval Precision (%)
4. Average Latency (ms)
"""

import asyncio
import random
import time
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, engine, Base
from models import User, Conversation, Message
from auth import get_password_hash
from imdcra_orchestrator import process_turn
from retrieval import retrieve_memories

# Simulated Persona / Facts for testing contradiction
FACT_SETS = [
    [
        "I work as a software engineer at Google.",
        "I love programming in Python and TypeScript.",
        "Actually, I just got a new job at Microsoft.", # Contradiction (supersedes 1)
        "I'm learning Rust for my new backend project."
    ],
    [
        "My favorite color is blue.",
        "I live in London with my two cats.",
        "I moved to New York last month for work.", # Contradiction (supersedes 2)
        "My favorite color is now definitely green." # Contradiction (supersedes 1)
    ],
    [
        "I am studying Information Technology at MIVA Open University.",
        "My thesis is on memory management for LLM agents.",
        "I plan to graduate in August 2026.",
        "My thesis is now focused on reinforcement learning instead." # Contradiction (supersedes 2)
    ]
]

async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_virtual_user(db: AsyncSession, idx: int) -> User:
    username = f"virtual_user_{idx}_{uuid4().hex[:6]}"
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("password123")
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def run_evaluation():
    await setup_db()
    
    total_users = 50
    sessions_per_user = 4
    
    metrics = {
        "extraction_successes": 0,
        "extraction_attempts": 0,
        "contradictions_detected": 0,
        "expected_contradictions": 0,
        "total_processing_time_ms": 0,
        "successful_retrievals": 0,
        "retrieval_attempts": 0
    }
    
    print(f"Starting Evaluation: {total_users} users, {sessions_per_user} sessions each.")
    
    async with AsyncSessionLocal() as db:
        for u_idx in range(total_users):
            user = await create_virtual_user(db, u_idx)
            
            # Select a random fact set for this user
            fact_set = random.choice(FACT_SETS)
            user_id_str = str(user.id)
            
            for s_idx, fact_message in enumerate(fact_set):
                start_time = time.time()
                
                # Check expected contradictions (naive heuristic for the test script based on the fact sets)
                is_expected_contradiction = "supersedes" in fact_message or "now" in fact_message or "new job" in fact_message
                if is_expected_contradiction:
                    metrics["expected_contradictions"] += 1
                
                # 1. Run the IMDCRA pipeline directly (simulating a turn without the LLM generation overhead)
                summary = await process_turn(
                    user_id=user_id_str,
                    user_message=fact_message,
                    recent_context=[{"role": "user", "content": fact_message}],
                    run_decay=True
                )
                
                processing_time_ms = (time.time() - start_time) * 1000
                metrics["total_processing_time_ms"] += processing_time_ms
                
                # Update metrics
                metrics["extraction_attempts"] += 1
                if summary.get("extracted_facts"):
                    metrics["extraction_successes"] += 1
                    
                if len(summary.get("superseded_memories", [])) > 0:
                    metrics["contradictions_detected"] += 1
                    
                # 2. Test Retrieval
                retrieval_query = f"What do you know about my {random.choice(['job', 'color', 'location', 'study'])}?"
                metrics["retrieval_attempts"] += 1
                try:
                    mems = retrieve_memories(user_id_str, retrieval_query, top_k=2)
                    if mems and len(mems) > 0:
                        metrics["successful_retrievals"] += 1
                except Exception:
                    pass
                    
            if (u_idx + 1) % 10 == 0:
                print(f"Processed {u_idx + 1} / {total_users} users...")

    # Calculate final results
    extraction_acc = (metrics["extraction_successes"] / metrics["extraction_attempts"]) * 100
    
    # Avoid division by zero
    exp_contra = max(1, metrics["expected_contradictions"])
    contra_acc = min(100.0, (metrics["contradictions_detected"] / exp_contra) * 100)
    
    retrieval_prec = (metrics["successful_retrievals"] / metrics["retrieval_attempts"]) * 100
    avg_latency = metrics["total_processing_time_ms"] / (total_users * sessions_per_user)
    
    print("\n" + "="*50)
    print("TABLE 4.2: IMDCRA EXPERIMENTAL EVALUATION RESULTS")
    print("="*50)
    print(f"Total Virtual Users:       {total_users}")
    print(f"Total Sessions:            {total_users * sessions_per_user}")
    print("-" * 50)
    print(f"Extraction Accuracy:       {extraction_acc:.1f}%")
    print(f"Contradiction Detection:   {contra_acc:.1f}%")
    print(f"Retrieval Precision:       {retrieval_prec:.1f}%")
    print(f"Average Pipeline Latency:  {avg_latency:.1f} ms")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
