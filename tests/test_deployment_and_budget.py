from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx
import pytest

from app.ai import AIError, Models, Summary
from app.budget import Budget, BudgetExceeded
from app.config import Settings
from app.main import create_app
from app.store import Store


def make_budget(tmp_path,**kwargs):
    store=Store(Settings(database=tmp_path/'budget.sqlite3',**kwargs))
    return store,Budget(store)

PAYLOAD={'model':'gpt-5.6-luna','input':'A bounded refund request','max_output_tokens':1600}


def test_concurrent_reservations_cannot_exceed_budget(tmp_path):
    store,budget=make_budget(tmp_path,monthly_budget_usd='0.004')
    def reserve(_):
        try:return budget.reserve('/responses',PAYLOAD)
        except BudgetExceeded:return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        requests=list(pool.map(reserve,range(6)))
    assert sum(bool(r) for r in requests)==1
    assert budget.summary()['monthly_accounted_usd']<=0.004


def test_usage_settlement_frees_reserved_headroom(tmp_path):
    store,budget=make_budget(tmp_path)
    rid=budget.reserve('/responses',PAYLOAD)
    reserved=budget.summary()['monthly_accounted_usd']
    budget.settle(rid,{'usage':{'input_tokens':100,'output_tokens':20}})
    assert budget.summary()['monthly_accounted_usd']==0.000044
    assert budget.summary()['monthly_accounted_usd']<reserved
    assert budget.summary()['unreconciled_requests']==0


def test_failed_calls_retain_reservations_across_restarts(tmp_path):
    store,budget=make_budget(tmp_path,monthly_budget_usd='0.004')
    rid=budget.reserve('/responses',PAYLOAD)
    budget.settle(rid)
    restarted=Budget(Store(store.settings))
    with pytest.raises(BudgetExceeded):restarted.reserve('/responses',PAYLOAD)
    assert restarted.summary()['unreconciled_requests']==1


def test_budget_windows_reset_in_utc(tmp_path):
    store,_=make_budget(tmp_path,daily_budget_usd='0.004',monthly_budget_usd='0.01')
    current=[datetime(2026,10,30,12,tzinfo=timezone.utc)]
    budget=Budget(store,clock=lambda:current[0])
    budget.reserve('/responses',PAYLOAD)
    with pytest.raises(BudgetExceeded):budget.reserve('/responses',PAYLOAD)
    current[0]+=timedelta(days=1)
    budget.reserve('/responses',PAYLOAD)
    assert budget.summary()['requests_this_month']==2
    current[0]+=timedelta(days=1)
    assert budget.summary()['requests_this_month']==0


def test_unknown_models_fail_closed(tmp_path):
    store,budget=make_budget(tmp_path)
    with pytest.raises(BudgetExceeded):budget.reserve('/responses',{**PAYLOAD,'model':'unknown-price-model'})
    assert budget.summary()['requests_this_month']==0


def test_live_transport_records_usage_without_secrets(tmp_path):
    store,budget=make_budget(tmp_path)
    settings=Settings(provider='openai',api_key='fake-private-test-key')
    models=Models(settings,budget)
    def respond(request):
        body=json.loads(request.content)
        assert body['model']=='gpt-5.6-luna'
        assert body['reasoning']=={'effort':'none'}
        assert body['store'] is False
        return httpx.Response(200,json={'usage':{'input_tokens':200,'output_tokens':30},
            'output':[{'type':'message','content':[{'type':'output_text','text':'{"summary":"Verified result"}'}]}]})
    client=httpx.Client(transport=httpx.MockTransport(respond))
    with patch('app.ai.httpx.Client',return_value=client):
        assert models.structured('Response aggregator',{'case':'synthetic'},Summary).summary=='Verified result'
    row=store.one('SELECT * FROM rg_ai_requests')
    assert row['status']=='complete'
    assert row['actual_micros']==76
    assert 'fake-private-test-key' not in json.dumps(row)
    assert 'synthetic' not in json.dumps(row)


def test_budget_exhaustion_sends_no_http_request(tmp_path):
    store,budget=make_budget(tmp_path,monthly_budget_usd='0')
    models=Models(Settings(provider='openai',api_key='fake-test-key'),budget)
    with patch('app.ai.httpx.Client') as client,pytest.raises(AIError,match='budget'):
        models.structured('Response aggregator',{},Summary)
    client.assert_not_called()


def test_live_app_starts_without_any_openai_calls(tmp_path):
    with patch('app.ai.httpx.Client') as client:
        app=create_app(Settings(database=tmp_path/'startup.sqlite3',provider='openai',api_key='fake-test-key'))
    client.assert_not_called()
    assert app.state.budget.summary()['requests_this_month']==0
    assert app.state.store.one('SELECT COUNT(*) AS count FROM rg_documents')['count']>0
    assert app.state.store.one('SELECT COUNT(*) AS count FROM rg_chunks')['count']==0


def test_railway_health_probe_is_narrowly_allowed(tmp_path):
    app=create_app(Settings(database=tmp_path/'railway.sqlite3',production=True,railway=True,origin='https://refundguard.example.test'))
    client=TestClient(app,base_url='http://healthcheck.railway.app')
    assert client.get('/health').status_code==200
    assert client.get('/api/auth/status').status_code==400
    assert client.get('/').status_code==400
    assert client.get('/health/').status_code==400
    public=TestClient(app,base_url='https://refundguard.example.test')
    assert public.get('/').status_code==200
    assert public.get('/health',headers={'Host':'evil.example.test'}).status_code==400


def test_railway_origin_derives_from_platform_environment(monkeypatch):
    monkeypatch.setenv('RAILWAY_PROJECT_ID','test-project')
    monkeypatch.setenv('RAILWAY_PUBLIC_DOMAIN','refundguard-test.up.railway.app')
    monkeypatch.delenv('APP_ORIGIN',raising=False)
    monkeypatch.delenv('APP_ENV',raising=False)
    settings=Settings.from_env()
    settings.validate()
    assert settings.railway and settings.production
    assert settings.origin=='https://refundguard-test.up.railway.app'


def test_invalid_budgets_cannot_disable_controls():
    for value in ('NaN','Infinity','-1','not-a-number'):
        with pytest.raises(ValueError):Settings(monthly_budget_usd=value).validate()


def test_container_command_uses_dynamic_port_and_single_worker():
    path=Path(__file__).parents[1]/'entrypoint.py'
    spec=importlib.util.spec_from_file_location('refundguard_entrypoint',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args=module.command({'PORT':'9876','RAILWAY_PROJECT_ID':'test'})
    assert args[args.index('--port')+1]=='9876'
    assert args[args.index('--workers')+1]=='1'
    assert args[args.index('--forwarded-allow-ips')+1]=='*'
    with pytest.raises(ValueError):module.command({'PORT':'0'})


def test_provider_error_cannot_echo_secret_to_the_app(tmp_path):
    store,budget=make_budget(tmp_path)
    marker='fake-private-api-key-should-never-be-returned'
    models=Models(Settings(provider='openai',api_key=marker),budget)
    client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(401,json={'error':marker})))
    with patch('app.ai.httpx.Client',return_value=client),pytest.raises(AIError) as error:
        models.structured('Response aggregator',{},Summary)
    assert marker not in str(error.value)
    assert budget.summary()['unreconciled_requests']==1
