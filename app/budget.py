"""Conservative local API budget accounting; never stores prompts or credentials.

Rates are USD per million tokens (numerically microdollars/token). Reservations
use a byte-based input upper estimate, schema overhead, and the full output cap.
Unknown/failed calls keep their reservations, since billing may have occurred.
This is application-side control at documented rates, not an OpenAI billing cap.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import json
from uuid import uuid4

PRICES={
    'gpt-5.6-luna':(Decimal('0.20'),Decimal('1.20')),
    'gpt-5.4-mini':(Decimal('0.75'),Decimal('4.50')),
    'text-embedding-3-small':(Decimal('0.02'),Decimal('0')),
}

class BudgetExceeded(Exception):
    pass

def micros(usd):
    return int((Decimal(usd)*1000000).to_integral_value(rounding=ROUND_CEILING))

def charge(model, inputs, outputs):
    if model not in PRICES:
        raise BudgetExceeded('This model has no configured price. Live requests are blocked until its price is reviewed.')
    input_rate,output_rate=PRICES[model]
    return int((input_rate*inputs+output_rate*outputs).to_integral_value(rounding=ROUND_CEILING))

class Budget:
    def __init__(self,store,clock=None):
        self.store=store
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.daily=micros(store.settings.daily_budget_usd)
        self.monthly=micros(store.settings.monthly_budget_usd)

    def reserve(self,path,payload):
        now=self.clock().astimezone(timezone.utc).isoformat()
        model=payload['model']
        # UTF-8 bytes conservatively bound the byte-level tokenization of text;
        # the additional allowance covers schema/message framing overhead.
        estimated_inputs=len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))+8192
        estimated_outputs=payload.get('max_output_tokens',0)
        estimate=charge(model,estimated_inputs,estimated_outputs)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT timestamp,COALESCE(actual_micros,reserved_micros) AS cost '
                            'FROM rg_ai_requests WHERE substr(timestamp,1,7)=?',(now[:7],)).fetchall()
            month=sum(r['cost'] for r in rows)
            day=sum(r['cost'] for r in rows if r['timestamp'][:10]==now[:10])
            if day+estimate>self.daily or month+estimate>self.monthly:
                raise BudgetExceeded('The application API budget is exhausted or has insufficient reserved headroom. '
                                     'No new API request was sent. Ask the administrator to review usage.')
            rid=str(uuid4())
            db.execute('INSERT INTO rg_ai_requests(id,timestamp,endpoint,model,reserved_micros,status) VALUES(?,?,?,?,?,?)',
                       (rid,now,path,model,estimate,'reserved'))
        return rid

    def settle(self,rid,result=None):
        row=self.store.one('SELECT model,reserved_micros FROM rg_ai_requests WHERE id=?',(rid,))
        usage=(result or {}).get('usage') or {}
        actual=None
        inputs=usage.get('input_tokens',usage.get('prompt_tokens',usage.get('total_tokens')))
        outputs=usage.get('output_tokens',0)
        if type(inputs) is int and inputs>=0 and type(outputs) is int and outputs>=0:
            actual=charge(row['model'],inputs,outputs)
        self.store.execute('UPDATE rg_ai_requests SET actual_micros=?,input_tokens=?,output_tokens=?,status=? WHERE id=?',
                           (actual,inputs if type(inputs) is int else None,outputs if type(outputs) is int else None,
                            'complete' if actual is not None else 'unknown',rid))

    def summary(self):
        now=self.clock().astimezone(timezone.utc).isoformat()
        rows=self.store.all('SELECT timestamp,COALESCE(actual_micros,reserved_micros) AS cost,status '
                            'FROM rg_ai_requests WHERE substr(timestamp,1,7)=?',(now[:7],))
        month=sum(r['cost'] for r in rows)
        day=sum(r['cost'] for r in rows if r['timestamp'][:10]==now[:10])
        return {'daily_limit_usd':self.daily/1000000,'monthly_limit_usd':self.monthly/1000000,
                'daily_accounted_usd':day/1000000,'monthly_accounted_usd':month/1000000,
                'monthly_remaining_usd':max(0,self.monthly-month)/1000000,
                'requests_this_month':len(rows),'unreconciled_requests':sum(r['status']!='complete' for r in rows),
                'basis':'Conservative local accounting, not the provider invoice; failed or unknown calls retain reservations.'}
