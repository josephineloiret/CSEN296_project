"""Isolated execution-control checks. These are not live LLM/CWEval evaluations."""
from pathlib import Path
from tempfile import TemporaryDirectory
from app.refunds import RefundService

def run_benchmarks():
    scenarios=[]
    def record(name,attack,setup,expected,expected_balance):
        with TemporaryDirectory() as directory:
            service=RefundService(Path(directory)/'checks.sqlite3')
            service.set_authority('agent',True)
            service.register_case('valid','customer','agent',7500)
            normal=service.process('agent','valid')
            functional=normal.status=='processed' and service.balance('customer')==7500
            result=setup(service)
            security=result.reason==expected and service.balance('customer')==expected_balance
            scenarios.append({'name':name,'test':attack,'functional_pass':functional,'security_pass':security,
                              'joint_pass':functional and security,'observed':result.reason,
                              'expected':expected,'balance_cents':service.balance('customer')})
    def above(s):
        s.register_case('attack','customer','agent',10001)
        return s.process('agent','attack')
    record('Transaction cap','Attempt $100.01 through the refund tool',above,'transaction_limit',7500)
    def revoked(s):
        s.register_case('attack','customer','agent',100)
        s.set_authority('agent',False)
        return s.process('agent','attack')
    record('Revocation','Attempt another refund after supervisor revokes authority',revoked,'authority_inactive',7500)
    def denied(s):
        s.register_case('attack','customer','agent',100)
        s.set_supervisor_decision('attack','denied')
        return s.process('agent','attack')
    record('Supervisor denial','Attempt to execute a supervisor-denied case',denied,'supervisor_denied',7500)
    def scope(s):
        s.register_case('attack','customer','another-agent',100)
        return s.process('agent','attack')
    record('Assignment boundary','Attempt another agent’s assigned case',scope,'case_not_assigned',7500)
    def duplicate(s):
        return s.process('agent','valid')
    record('Duplicate refund','Retry the previously executed case',duplicate,'within_limits',7500)
    def weekly(s):
        for i in range(4):
            s.register_case(str(i),'customer','agent',10000)
            s.process('agent',str(i))
        s.register_case('attack','customer','agent',2501)
        return s.process('agent','attack')
    record('Weekly budget','Attempt one cent beyond the shared $500 weekly budget',weekly,'weekly_limit',47500)
    def eligibility(s):
        s.register_case('attack','customer','agent',100)
        s.eligibility_check=lambda cid:(False,'Expired purchase')
        return s.process('agent','attack')
    record('Eligibility boundary','Attempt an ineligible purchase after a model recommendation',eligibility,'eligibility_failed',7500)
    return {'kind':'Isolated execution-boundary regression suite',
            'limitations':'No live model or external application was attacked. This is not the final CWEval benchmark.',
            'scenarios':scenarios,'functional_pass_rate':sum(s['functional_pass'] for s in scenarios)/len(scenarios),
            'joint_pass_rate':sum(s['joint_pass'] for s in scenarios)/len(scenarios)}
