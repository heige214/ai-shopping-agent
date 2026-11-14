import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import asyncpg

BACKEND_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = BACKEND_DIR / "seeds" / "knowledge" / "knowledge.json"


def fetch_all(query: str, *params) -> list[asyncpg.Record]:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def _run():
        connection = await asyncpg.connect(dsn)
        try:
            return await connection.fetch(query, *params)
        finally:
            await connection.close()

    return asyncio.run(_run())


def fetch_int(query: str, *params) -> int:
    rows = fetch_all(query, *params)
    return int(rows[0][0]) if rows else 0


def run_seed(args: list[str], extra_env: dict | None = None):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "scripts.seed_knowledge", *args],
        cwd=BACKEND_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def write_sample_knowledge(path: Path, chunks: list[dict]) -> Path:
    document = {
        "version": 1,
        "documents": [
            {
                "seed_key": "product:TEST-A:sample",
                "scope": "product",
                "product_code": "TEST-A",
                "doc_type": "detail",
                "title": "TEST-A 测试衬衫 · 商品详情",
                "source": "seed",
                "chunks": chunks,
            }
        ],
    }
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def test_migration_creates_knowledge_and_support_tables(migrated_database):
    tables = {
        row["tablename"]
        for row in fetch_all(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
    }
    assert {
        "knowledge_documents",
        "knowledge_chunks",
        "chat_sessions",
        "chat_messages",
        "support_tickets",
    } <= tables
    assert "chat_actions" not in tables
    assert "knowledge_candidates" not in tables
    assert "product_field_history" not in tables

    indexes = {
        row["indexname"]
        for row in fetch_all(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
        )
    }
    assert "ix_knowledge_chunks_embedding_hnsw" in indexes
    assert "ix_knowledge_chunks_search_text_gin" in indexes
    assert "ix_chat_messages_session_created" in indexes
    assert "ix_support_tickets_status_created" in indexes

    columns = {
        row["column_name"]
        for row in fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'knowledge_chunks'"
        )
    }
    assert {"embedding", "search_text", "meta", "product_id", "category_id"} <= columns


def test_build_knowledge_seed_counts_and_pending_drafts(tmp_path):
    output = tmp_path / "knowledge"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.build_knowledge_seed",
            "--output-dir",
            str(output),
        ],
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "913 文档 / 1813 chunk" in result.stdout

    data = json.loads((output / "knowledge.json").read_text(encoding="utf-8"))
    documents = data["documents"]
    assert len(documents) == 913
    counts: dict[str, int] = {}
    for document in documents:
        counts[document["doc_type"]] = counts.get(document["doc_type"], 0) + len(
            document["chunks"]
        )
    assert counts == {
        "detail": 600,
        "size": 300,
        "faq": 900,
        "care": 4,
        "policy": 9,
    }
    assert not any(
        document["scope"] == "category" and document["doc_type"] == "faq"
        for document in documents
    )

    drafts = json.loads(
        (output / "category_faq_drafts.json").read_text(encoding="utf-8")
    )["drafts"]
    assert len(drafts) == 24
    assert all(draft["status"] == "pending" for draft in drafts)

    review_lines = (output / "review.csv").read_text(
        encoding="utf-8-sig"
    ).splitlines()
    assert len(review_lines) == 1 + 1813 + 24
    assert review_lines[0].startswith("层级,文档类型")
    assert any(",pending" in line for line in review_lines)


def test_seed_knowledge_full_counts_and_idempotency(clean_support, seeded_catalog):
    result = run_seed([], {"AI_PROVIDER": "fake"})
    assert result.returncode == 0, result.stderr
    assert "文档 913" in result.stdout
    assert "新增 chunk 1813" in result.stdout

    counts = fetch_all(
        "SELECT "
        "(SELECT count(*) FROM knowledge_documents), "
        "(SELECT count(*) FROM knowledge_chunks), "
        "(SELECT count(*) FROM knowledge_chunks WHERE embedding IS NOT NULL)"
    )[0]
    assert tuple(counts) == (913, 1813, 1813)
    assert (
        fetch_int(
            "SELECT count(*) FROM knowledge_documents "
            "WHERE scope = 'category' AND doc_type = 'faq'"
        )
        == 0
    )
    assert (
        fetch_int(
            "SELECT count(*) FROM knowledge_documents WHERE doc_type = 'policy'"
        )
        == 9
    )

    # 再跑一次不应新增
    again = run_seed([], {"AI_PROVIDER": "fake"})
    assert again.returncode == 0, again.stderr
    assert "新增 chunk 0" in again.stdout
    assert (
        fetch_int("SELECT count(*) FROM knowledge_chunks") == 1813
    )


def test_seed_without_key_stores_null_embeddings_then_backfills(
    clean_support, sample_catalog, tmp_path
):
    sample = write_sample_knowledge(
        tmp_path / "small.json",
        [
            {
                "seed_key": "product:TEST-A:sample:1",
                "content": "测试衬衫的材质是纯棉，适合春夏。",
                "meta": {"doc_type": "detail", "seed_key": "product:TEST-A:sample:1"},
            },
            {
                "seed_key": "product:TEST-A:sample:2",
                "content": "测试衬衫建议 30℃ 以下冷水洗涤。",
                "meta": {"doc_type": "detail", "seed_key": "product:TEST-A:sample:2"},
            },
        ],
    )
    result = run_seed(
        ["--file", str(sample)],
        {"AI_PROVIDER": "local", "DASHSCOPE_API_KEY": ""},
    )
    assert result.returncode == 0, result.stderr
    assert "新增 chunk 2" in result.stdout
    assert (
        fetch_int(
            "SELECT count(*) FROM knowledge_chunks WHERE embedding IS NOT NULL"
        )
        == 0
    )

    backfill = run_seed(
        ["--embeddings-only"],
        {"AI_PROVIDER": "fake", "DASHSCOPE_API_KEY": ""},
    )
    assert backfill.returncode == 0, backfill.stderr
    assert "写入 2" in backfill.stdout
    assert (
        fetch_int(
            "SELECT count(*) FROM knowledge_chunks WHERE embedding IS NOT NULL"
        )
        == 2
    )


def test_seed_dedupes_identical_chunks_in_same_scope(
    clean_support, sample_catalog, tmp_path
):
    sample = write_sample_knowledge(
        tmp_path / "duplicate.json",
        [
            {
                "seed_key": "product:TEST-A:dup:1",
                "content": "测试衬衫的材质是纯棉，版型常规。",
                "meta": {"doc_type": "detail", "seed_key": "product:TEST-A:dup:1"},
            },
            {
                "seed_key": "product:TEST-A:dup:2",
                "content": "测试衬衫的材质是纯棉，版型常规。",
                "meta": {"doc_type": "detail", "seed_key": "product:TEST-A:dup:2"},
            },
        ],
    )
    result = run_seed(["--file", str(sample)], {"AI_PROVIDER": "fake"})
    assert result.returncode == 0, result.stderr
    assert "新增 chunk 1" in result.stdout
    assert "去重跳过 1" in result.stdout
    assert fetch_int("SELECT count(*) FROM knowledge_chunks") == 1
