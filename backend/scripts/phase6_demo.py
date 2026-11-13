"""No secrets/no side effects demo for agent orchestration."""
from app.phase6_agents.graph import propose
print(propose({'kind':'interview_reminder','candidate_name':'Fictional Candidate','job_title':'Tool Developer','scheduled':'tomorrow at 11 AM'}))
print('No emails sent; explicit approval required before execution.')
