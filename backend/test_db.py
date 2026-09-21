import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect(
        'postgresql://postgres.fxwmgjnuypymydvvcipd:Vkhw%2B7BNSz9.J6c@aws-1-eu-west-3.pooler.supabase.com:5432/postgres',
        ssl='require'
    )
    try:
        result = await conn.fetchrow(
            'INSERT INTO users (username, email, hashed_password) VALUES ($1, $2, $3) RETURNING id, username, email',
            'testuser99', 'testuser99@test.com', 'fakehash'
        )
        print(f'Insert OK: {result}')
        await conn.execute('DELETE FROM users WHERE username = $1', 'testuser99')
        print('Cleanup OK')
    except Exception as e:
        print(f'Insert failed: {type(e).__name__}: {e}')
    await conn.close()

asyncio.run(test())
