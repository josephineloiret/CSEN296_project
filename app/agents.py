"""Specialist agents have narrow inputs; none receives an unrestricted tool registry."""
import re
from app.ai import AIError, Recommendation, Draft

_EXTERNAL_LINK_RE = re.compile(
    r'https?://|\[[^\]]+\]\(\s*[^)]+\)|\[[^\]]+\]\s*\[[^\]]*\]',
    re.IGNORECASE,
)

class IntakeAgent:
    def __init__(self, store):
        self.store=store

    def assign(self, case_id):
        case=self.store.one('SELECT r.customer_id,c.agent_id FROM rg_cases r JOIN cases c ON c.id=r.id WHERE r.id=?',(case_id,))
        if not case or case['agent_id']!='refund-agent':
            raise AIError('No authorized agent assignment exists for this case')
        return {'case_id':case_id,'assigned_agent':case['agent_id'],'customer_id':case['customer_id']}

class RecordsAgent:
    def __init__(self, store, knowledge, case_files):
        self.store,self.knowledge=store,knowledge
        self.case_files=case_files

    def retrieve(self, case_id, query):
        case=self.store.one('SELECT customer_id FROM rg_cases WHERE id=?',(case_id,))
        if not case:
            raise AIError('No authorized records scope exists for this case')
        return self.knowledge.search(query,case['customer_id'])

    def retrieve_case_files(self, case_id, query, user):
        return self.case_files.search(case_id, query, user)

    def case_file_evidence(self, case_id, query, user):
        """Drive passages for the workflow, limited to what the running user may read."""
        return self.case_files.workflow_passages(case_id, query, user)


class RefundsAgent:
    def __init__(self, models):
        self.models=models

    def recommend(self, case, messages, context, eligible, eligibility_reason):
        if self.models.settings.provider=='local':
            return Recommendation(decision='approve' if eligible else 'review',rationale=eligibility_reason,
                                  source_ids=list(dict.fromkeys(x['source_id'] for x in context)))
        result=self.models.structured('Refunds agent',{
            'case_id':case['id'],'request':{'amount_cents':case['amount_cents'],'reason':case['reason_code'],'messages':messages},
            'verified_eligibility':eligible,'eligibility_reason':eligibility_reason,
            'supervisor':case['supervisor'],'retrieved_evidence':context},Recommendation)
        if not set(result.source_ids).issubset({item['source_id'] for item in context}):
            raise AIError('The model cited an unavailable source. Supervisor review is required.')
        return result

class EmailAgent:
    def __init__(self, models):
        self.models=models

    def draft(self, outcome):
        if self.models.settings.provider=='openai':
            draft = self.models.structured('Email agent',outcome,Draft)
            if _EXTERNAL_LINK_RE.search(draft.subject) or _EXTERNAL_LINK_RE.search(draft.body):
                return None
            return draft
        return None

class ReportingAgent:
    def __init__(self, store):
        self.store=store

    def outcome(self, case_id):
        row=self.store.one('SELECT r.id AS case_id,r.status,r.rationale AS reason,c.amount_cents '
                           'FROM rg_cases r JOIN cases c ON r.id=c.id WHERE r.id=?',(case_id,))
        if not row:
            raise AIError('No recorded outcome exists')
        row['refund_executed']=bool(self.store.one('SELECT case_id FROM ledger WHERE case_id=?',(case_id,)))
        return row
