"""Integration smoke tests for Phase 3 pipeline.
Requires Docker stack: make up
"""
import asyncio
import pytest
import asyncpg

POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5433/cryptoswarm"


@pytest.mark.integration
async def test_phase3_tables_exist():
    """Verify all Phase 3 tables were created by migration."""
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )
        names = {r["tablename"] for r in tables}
        for expected in ["news_items", "news_sentiment", "agent_prompts",
                         "ml_signals", "training_runs"]:
            assert expected in names, f"Table {expected!r} missing"
    finally:
        await conn.close()


@pytest.mark.integration
async def test_news_item_insert_and_retrieve():
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        news_id = await conn.fetchval(
            """
            INSERT INTO news_items (source, url, title, body)
            VALUES ('test', 'https://test.com/smoke-1', 'Test Title', 'Test body')
            ON CONFLICT (url) DO UPDATE SET title=EXCLUDED.title
            RETURNING id
            """
        )
        assert news_id is not None
        await conn.execute(
            """
            INSERT INTO news_sentiment
              (news_item_id, symbol, model, relevance, score, summary)
            VALUES ($1, 'BTCUSDT', 'qwen2.5:7b', 0.9, 0.7, 'Smoke test')
            """,
            news_id,
        )
        rows = await conn.fetch(
            "SELECT score FROM news_sentiment WHERE symbol='BTCUSDT' AND news_item_id=$1",
            news_id,
        )
        assert len(rows) >= 1
        assert float(rows[0]["score"]) == 0.7
    finally:
        await conn.close()


@pytest.mark.integration
async def test_agent_prompt_versioning():
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM agent_prompts WHERE agent_name='smoke_test'")
        await conn.execute(
            """
            INSERT INTO agent_prompts (agent_name, version, system_prompt, active)
            VALUES ('smoke_test', 1, 'Version 1 prompt', true)
            """
        )
        await conn.execute(
            """
            UPDATE agent_prompts SET active=false WHERE agent_name='smoke_test';
            INSERT INTO agent_prompts (agent_name, version, system_prompt, active)
            VALUES ('smoke_test', 2, 'Version 2 evolved prompt', true)
            """
        )
        row = await conn.fetchrow(
            "SELECT system_prompt FROM agent_prompts WHERE agent_name='smoke_test' AND active=true"
        )
        assert row["system_prompt"] == "Version 2 evolved prompt"
    finally:
        await conn.close()
