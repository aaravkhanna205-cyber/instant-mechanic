"""Redis-backed background resume extraction with retry and idempotent updates."""
import json
import logging
import os
from uuid import UUID
import redis
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.phase4_ai.documents import extract_text,reviewable_skills,chunks
from app.phase4_ai.storage import path_for,save_bytes
from app.phase4_ai.vectors import embed,MODEL_ID

log=logging.getLogger(__name__)
QUEUE='imhire:phase4:queue'
INFLIGHT='imhire:phase4:inflight'

def process_one(engine, document_id: UUID):
    with engine.connect() as conn:
        row=conn.execute(text('SELECT filename, file_ext FROM phase4_documents WHERE id=:id'),{'id':document_id}).first()
    if row is None: return
    filename,ext=row
    file=path_for(document_id,ext)
    content=extract_text(filename,file.read_bytes())
    snippets=chunks(content)
    vectors=embed(snippets)
    skills=reviewable_skills(content)
    # Store extraction in private folder, never on a public web route.
    txt=path_for(document_id,'txt')
    if not txt.exists(): save_bytes(document_id,'txt',content.encode('utf-8'))
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM phase4_chunks WHERE document_id=:id'),{'id':document_id})
        for i,(snippet,vector) in enumerate(zip(snippets,vectors)):
            conn.execute(text('INSERT INTO phase4_chunks(document_id,position,excerpt,embedding,model_id) VALUES (:id,:pos,:excerpt,CAST(:vector AS vector),:model)'),
                         {'id':document_id,'pos':i,'excerpt':snippet[:1000],'vector':'['+','.join(map(str,vector))+']','model':MODEL_ID})
        conn.execute(text("UPDATE phase4_documents SET status='ready', skills=CAST(:skills AS jsonb), processed_at=now(), error=NULL WHERE id=:id"),{'id':document_id,'skills':json.dumps(skills)})

def main():
    r=redis.Redis.from_url(settings.redis_url,decode_responses=True)
    engine=create_engine(settings.database_url,pool_pre_ping=True)
    # Recover any jobs orphaned by worker crash. Processing is idempotent.
    for item in r.lrange(INFLIGHT,0,-1):
        r.lpush(QUEUE,item)
        r.lrem(INFLIGHT,1,item)
    print('Phase 4 worker listening for resume jobs. Ctrl+C to stop.',flush=True)
    while True:
        raw=r.brpoplpush(QUEUE,INFLIGHT,timeout=5)
        if raw is None: continue
        try:
            job=json.loads(raw);document_id=UUID(job['id']);attempt=int(job.get('attempt',0))
            try:
                process_one(engine,document_id)
            except Exception:
                log.exception('Resume processing failed: %s',document_id)
                if attempt < 2:
                    r.lpush(QUEUE,json.dumps({'id':str(document_id),'attempt':attempt+1}))
                else:
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE phase4_documents SET status='failed',error='Processing failed; contact administrator' WHERE id=:id"),{'id':document_id})
        finally:
            r.lrem(INFLIGHT,1,raw)
if __name__=='__main__': main()
