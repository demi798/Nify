#!/usr/bin/env python3
"""Milvus 最小可跑通示例：建集合 → 插入向量 → 相似度查询。

两种连接方式（二选一）：
1) Milvus Lite（默认，无需 Docker，落盘到本地 .db）
2) Standalone 服务：export MILVUS_URI=http://127.0.0.1:19530

依赖安装（在 backend venv 中）：
  pip install 'pymilvus[milvus-lite]>=2.4.0,<3.0.0'

运行：
  python scripts/milvus_hello.py
"""

from __future__ import annotations

import os
import random

from pymilvus import DataType, MilvusClient

# 与 Nify .env 默认端口对齐；未设置则走 Lite
URI = os.environ.get("MILVUS_URI", "./milvus_hello.db")
COLLECTION = "hello_chunks"
DIM = 8  # 演示用小维度；正式 RAG 用 Embedding 模型真实 dim（如 1536）


def fake_embedding(seed: int) -> list[float]:
    """伪造向量；真实场景应调用 Embedding API / 本地模型。"""
    rng = random.Random(seed)
    vec = [rng.uniform(-1.0, 1.0) for _ in range(DIM)]
    # 简单 L2 归一化，便于 COSINE 检索
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]


def main() -> None:
    print(f"连接 Milvus: {URI}")
    client = MilvusClient(uri=URI)

    if client.has_collection(COLLECTION):
        client.drop_collection(COLLECTION)
        print(f"已删除旧集合 {COLLECTION}")

    # ---------- 1) 建「表」（Collection + Schema + 向量索引）----------
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("milvus_pk", DataType.VARCHAR, is_primary=True, max_length=36)
    schema.add_field("workspace_id", DataType.VARCHAR, max_length=36)
    schema.add_field("text", DataType.VARCHAR, max_length=512)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=DIM)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )

    client.create_collection(
        collection_name=COLLECTION,
        schema=schema,
        index_params=index_params,
    )
    print(f"已创建集合 {COLLECTION}（dim={DIM}, metric=COSINE）")

    # ---------- 2) 插入向量（正文可一并存；Nify 正式方案常只存 pk，正文回表 MySQL）----------
    rows = [
        {
            "milvus_pk": "chunk-001",
            "workspace_id": "ws-demo",
            "text": "退货政策：七天无理由退货",
            "embedding": fake_embedding(1),
        },
        {
            "milvus_pk": "chunk-002",
            "workspace_id": "ws-demo",
            "text": "运费说明：满 99 包邮",
            "embedding": fake_embedding(2),
        },
        {
            "milvus_pk": "chunk-003",
            "workspace_id": "ws-other",
            "text": "其他工作区文档，不应被 ws-demo 检索到",
            "embedding": fake_embedding(3),
        },
    ]
    client.insert(collection_name=COLLECTION, data=rows)
    print(f"已插入 {len(rows)} 条")

    # ---------- 3) 相似度查询（带 workspace 过滤，模拟多租户）----------
    query_vec = fake_embedding(1)  # 与 chunk-001 同种子 → 应最相似
    results = client.search(
        collection_name=COLLECTION,
        data=[query_vec],
        limit=3,
        filter='workspace_id == "ws-demo"',
        output_fields=["milvus_pk", "workspace_id", "text"],
        search_params={"metric_type": "COSINE"},
    )

    print("\n检索结果（仅 workspace_id=ws-demo）：")
    for hits in results:
        for hit in hits:
            # Lite / Standalone 返回结构略有差异，兼容 dict 与对象
            if isinstance(hit, dict):
                entity = hit.get("entity") or hit
                score = hit.get("distance", hit.get("score"))
                pk = entity.get("milvus_pk")
                text = entity.get("text")
            else:
                entity = hit.entity
                score = hit.distance
                pk = entity.get("milvus_pk")
                text = entity.get("text")
            print(f"  score={score:.4f}  pk={pk}  text={text}")

    client.close()
    print("\n完成。")


if __name__ == "__main__":
    main()
