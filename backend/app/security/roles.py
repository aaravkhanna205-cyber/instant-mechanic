"""The one place that says what each organization role may do.

Super Admin is not a role here: it is the account flag `is_platform_admin`, which can do
everything in every organization (create organizations, platform settings, data deletion).
"""

ALL_ROLES = ('owner', 'admin', 'hr_manager', 'hiring_manager', 'recruiter', 'interviewer', 'candidate')

# Everything inside their organization: jobs, candidates, interviews, decisions, agents,
# team members and roles, reports and exports, emails and notifications.
FULL_ACCESS = ('owner', 'admin', 'hr_manager', 'hiring_manager')

# Day-to-day recruiting: jobs, candidates, interviews, agents. Cannot manage the team.
RECRUITING = FULL_ACCESS + ('recruiter',)

# Anyone who works on the hiring side (can be chosen as an interviewer).
STAFF = RECRUITING + ('interviewer',)

# Roles that can be given to a team member (candidate accounts are created by applying).
TEAM_ROLES = STAFF

ROLE_INFO = {
    'owner': ('Owner', 'Full access to this organization. Usually the business owner.'),
    'admin': ('Organization admin', 'Full access to this organization.'),
    'hr_manager': ('HR manager', 'Full access: jobs, candidates, interviews, decisions, team, emails, reports and exports.'),
    'hiring_manager': ('Hiring manager', 'Full access: interviews, shortlisting, hiring decisions, team, reports and exports.'),
    'recruiter': ('Recruiter', 'Jobs, candidates, interviews and AI agents. Cannot manage the team.'),
    'interviewer': ('Interviewer', 'Can be assigned to interviews and give feedback.'),
    'candidate': ('Candidate', 'Applies to jobs and uses the candidate portal.'),
}


def role_list() -> list[dict]:
    return [{'role': role, 'label': ROLE_INFO[role][0], 'description': ROLE_INFO[role][1],
             'full_access': role in FULL_ACCESS, 'team_role': role in TEAM_ROLES} for role in ALL_ROLES]
