from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import json
from uuid import uuid4
from threading import BoundedSemaphore
import time
from fastapi import HTTPException
from app.ai import AGENTS, AIError, Plan, Summary
from app.store import stamp
from app.agents import IntakeAgent, RecordsAgent, RefundsAgent, EmailAgent, ReportingAgent

class Workflow:
    def __init__(self, store, knowledge, models):
        self.store, self.knowledge, self.models = store, knowledge, models
        self.intake=IntakeAgent(store)
        self.records=RecordsAgent(store,knowledge)
        self.refunds_agent=RefundsAgent(models)
        self.email_agent=EmailAgent(models)
        self.reporting=ReportingAgent(store)
        self.slots = BoundedSemaphore(store.settings.workflow_concurrency)

    def email(self, case_id, direction, subject, body):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            case = db.execute('SELECT r.id,p.email FROM rg_cases r JOIN rg_profiles p '
                              'ON p.id=r.customer_id WHERE r.id=?',(case_id,)).fetchone()
            authority = db.execute("SELECT active FROM authority WHERE agent_id='refund-agent'").fetchone()
            if not case or not authority or not authority['active']:
                return False
            db.execute('INSERT INTO rg_messages VALUES(?,?,?,?,?,?,?)',
                       (str(uuid4()),case_id,direction,subject[:200],body[:6000],case['email'],stamp()))
            return True

    def run(self, case_id, user):
        from app.execution import deadline
        if not self.slots.acquire(blocking=False):
            self.store.event(user['id'],'workflow.busy',case_id)
            raise HTTPException(429,'All workflow slots are busy. Try again shortly.',headers={'Retry-After':'5'})
        token = deadline.set(time.monotonic()+self.store.settings.workflow_timeout_seconds)
        try:
            return self._run_claimed(case_id,user)
        finally:
            deadline.reset(token)
            self.slots.release()

    def _run_claimed(self, case_id, user):
        case = self.store.case(case_id,user)
        if not case:
            raise ValueError('Case not found')
        if case['status'] in ('processed','denied'):
            return case
        if not self.store.authority_active():
            raise ValueError('Agent authority is paused. A supervisor must restore it.')
        run_id = str(uuid4())
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Recover abandoned claims after a crashed worker. Refund ledger is idempotent.
            cutoff = (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
            db.execute("UPDATE rg_cases SET status='review' WHERE id=? AND status='processing' AND updated_at<?",(case_id,cutoff))
            changed = db.execute("UPDATE rg_cases SET status='processing',run_id=?,updated_at=?,attempts=attempts+1 "
                                 "WHERE id=? AND status IN ('new','review','blocked')",(run_id,stamp(),case_id)).rowcount
            if not changed:
                raise ValueError('This case is already being processed')
        self.store.event(user['id'],'workflow.started',case_id,run_id=run_id,mode=self.models.mode)
        try:
            self._run(case,run_id)
        except Exception as exc:
            # Preserve actual execution even if a later model/email operation fails.
            ledger = self.store.one('SELECT decision_json FROM ledger WHERE case_id=?',(case_id,))
            message = str(exc) if isinstance(exc,AIError) else 'Workflow interrupted. Review the case and retry.'
            status = 'processed' if ledger else 'review'
            self.store.execute('UPDATE rg_cases SET status=?,rationale=?,updated_at=? WHERE id=?',
                               (status,message,stamp(),case_id))
            self.store.trace(run_id,case_id,'Orchestrator','error',{'message':message,'executed':bool(ledger)})
            self.store.event('orchestrator','workflow.interrupted',case_id,run_id=run_id,executed=bool(ledger))
            if isinstance(exc,AIError) and 'deadline' in str(exc).lower():
                self.store.event('orchestrator','workflow.timeout',case_id,executed=bool(ledger))
        return self.store.case(case_id,user)

    def _run(self, case, run_id):
        from app.execution import remaining
        remaining()
        cid = case['id']
        emit = lambda agent,operation,result:self.store.trace(run_id,cid,agent,operation,result)
        if self.models.settings.provider=='openai':
            plan = self.models.structured('Orchestrator',{'task':'Plan the refund workflow','case_id':cid,
                                                        'previous_outcome':case['summary']},Plan)
            if plan.steps != AGENTS:
                raise AIError('The proposed plan violated the permitted workflow. Supervisor review is required.')
        else:
            plan = Plan(steps=AGENTS,summary='Deterministic local workflow; no LLM called')
        emit('Orchestrator','plan',plan.model_dump())
        emit('Intake','assignment',self.intake.assign(cid))
        if not self.store.one("SELECT id FROM rg_messages WHERE case_id=? AND direction='outbound'",(cid,)):
            self.email(cid,'outbound','We received '+cid,'Your synthetic refund request has been received and assigned for review.')
        incoming=self.store.all("SELECT body FROM rg_messages WHERE case_id=? AND direction='inbound' ORDER BY created_at DESC LIMIT 5",(cid,))
        customer_content='\n'.join(m['body'] for m in reversed(incoming))[-12000:]
        context = self.records.retrieve(cid,customer_content+' refund '+case['reason_code'])
        remaining()
        emit('Records','retrieve',{'sources':context,'customer_id':case['customer_id'],'embedding':self.models.embedding_kind})
        eligible,eligibility_reason = self.store.eligibility(cid)
        recommendation=self.refunds_agent.recommend(case,customer_content,context,eligible,eligibility_reason)
        remaining()
        emit('Refunds','recommendation',recommendation.model_dump())
        if recommendation.decision=='approve':
            decision = self.store.refunds.process('refund-agent',cid)
            emit('Execution control','refund',asdict(decision))
            status = 'processed' if decision.status=='processed' else 'blocked'
            reason = decision.reason
            if status == 'blocked':
                self.store.event('refund-agent','refund.blocked',cid,reason=reason)
        else:
            status = 'denied' if recommendation.decision=='deny' else 'review'
            reason = recommendation.rationale
            emit('Execution control','not_executed',{'reason':reason})
        # A supervisor can deny while the model is working; do not overwrite that decision.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            control = db.execute('SELECT supervisor FROM cases WHERE id=?',(cid,)).fetchone()
            if control['supervisor']=='denied' and status!='processed':
                status,reason = 'denied','supervisor_denied'
            db.execute('UPDATE rg_cases SET status=?,rationale=?,updated_at=? WHERE id=?',
                       (status,reason,stamp(),cid))
        actual = {'case_id':cid,'status':status,'reason':reason,'amount_cents':case['amount_cents']}
        draft=self.email_agent.draft(actual)
        remaining()
        if draft:
            self.email(cid,'draft',draft.subject,draft.body)
        # Sent mock notices are generated from the execution result, never from model assertions.
        body = f"Case {cid}: {status}. Reason: {reason}. Requested refund: ${case['amount_cents']/100:.2f}. This is a mock notification."
        sent = self.email(cid,'outbound','Refund decision '+cid,body)
        emit('Email','mock_notification',{'sent':sent,'delivery':'local mock mailbox','model_draft_requires_review':True})
        actual=self.reporting.outcome(cid)
        emit('Reporting','record_outcome',actual)
        if self.models.settings.provider=='openai':
            summary = self.models.structured('Response aggregator',{'executed_outcome':actual},Summary).summary
        else:
            summary = f"{cid}: {status}. {reason}. Processed using local simulation; no LLM was called."
        self.store.execute('UPDATE rg_cases SET summary=? WHERE id=?',(summary[:6000],cid))
        emit('Orchestrator','aggregate',{'summary':summary})
        self.store.event('orchestrator','workflow.completed',cid,run_id=run_id,status=status,reason=reason)
