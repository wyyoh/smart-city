"""Append-only snapshots for v2; historical v1 tables are retained."""
import hashlib
import json
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Column, JSON
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel

from ..storage import now


class DecisionRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    kind: str = Field(index=True)
    created_at: str = Field(default_factory=now)
    dataset_id: str | None = None
    parent_id: str | None = Field(default=None, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def append_record(session, kind, payload, parent_id=None, dataset_id=None, record_id=None):
    record_id = record_id or kind[:4] + '_' + uuid4().hex
    body = {'id': record_id, 'kind': kind, 'created_at': now(), 'parent_id': parent_id, **payload}
    body['sha256'] = digest(body)
    record = DecisionRecord(id=record_id, kind=kind, created_at=body['created_at'],
                            parent_id=parent_id, dataset_id=dataset_id, payload=body)
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(DecisionRecord, record_id)
        if not existing or not payload.get('request_fingerprint') or existing.payload.get('request_fingerprint') != payload['request_fingerprint']:
            raise HTTPException(409, '幂等键已用于其他内容')
        return get_record(session, record_id)
    return body


def get_record(session, record_id, kind=None):
    record = session.get(DecisionRecord, record_id)
    if record is None or (kind is not None and record.kind != kind):
        raise HTTPException(404, '决策记录不存在')
    body = record.payload
    if digest({k: v for k, v in body.items() if k != 'sha256'}) != body['sha256']:
        raise HTTPException(409, '决策快照完整性检查失败')
    return body
