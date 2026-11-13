"""Free local agent graph: plan -> draft -> check -> request human approval.
LangGraph is optional for unit tests; production install adds it.
"""
from typing import TypedDict
from .policy import draft_message, validate_draft
from .local_llm import refine

class State(TypedDict, total=False):
    kind: str
    candidate_name: str
    job_title: str
    scheduled: str
    draft: str
    valid: bool
    stage: str

def plan(state: State)->State: return {'stage':'planned'}
def draft(state: State)->State:
    base=draft_message(state['kind'],state.get('candidate_name','Candidate'),state.get('job_title','the role'),when=state.get('scheduled',''))
    return {'draft':refine(state['kind'],base),'stage':'drafted'}
def policy_check(state: State)->State:
    validate_draft(state['kind'],state['draft'])
    return {'valid':True,'stage':'approval_required'}

def build_graph():
    from langgraph.graph import StateGraph, START, END
    g=StateGraph(State)
    g.add_node('plan',plan)
    g.add_node('draft',draft)
    g.add_node('policy',policy_check)
    g.add_edge(START,'plan');g.add_edge('plan','draft');g.add_edge('draft','policy');g.add_edge('policy',END)
    return g.compile()

def propose(state: State)->State:
    """Identical deterministic behavior whether LangGraph is installed or not."""
    try:
        return build_graph().invoke(state)
    except ImportError:
        state={**state,**plan(state)}
        state={**state,**draft(state)}
        return {**state,**policy_check(state)}
