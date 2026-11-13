"""Optional free, local Ollama draft refinement. Never sends messages or changes records.
No remote URLs accepted; all outputs pass the deterministic policy validator.
"""
import json,os
from urllib.request import Request,urlopen
from .policy import validate_draft

def refine(kind:str,draft:str)->str:
    from dotenv import load_dotenv
    load_dotenv(override=False)
    if os.getenv('PHASE6_ENABLE_LOCAL_LLM','NO').upper()!='YES':return draft
    model=os.getenv('PHASE6_OLLAMA_MODEL','gemma3:1b').strip()[:100]
    prompt=("You assist a human recruiter. Rewrite this administrative message in clear professional "
            "English. Do not introduce facts, dates, promises, employment decisions, requests for sensitive "
            "data, or new contact details. Respond with the rewritten message only.\n\n" + draft[:2000])
    request=Request('http://127.0.0.1:11434/api/generate',data=json.dumps({'model':model,'prompt':prompt,'stream':False,'options':{'temperature':0.1,'num_predict':250}}).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(request,timeout=12) as response:
            payload=json.loads(response.read(16000))
        rewritten=str(payload.get('response','')).strip()
        # A model cannot create a candidate decision and cannot extend the message arbitrarily.
        return validate_draft(kind,rewritten)
    except Exception:
        # A local model is OPTIONAL. Deterministic and reviewable fallback always works.
        return draft
