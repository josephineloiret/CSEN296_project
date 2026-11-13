"""Bucket 2: customer isolation and document lifecycle, without new role policy.

Fixtures and vectors are synthetic. Ranking is controlled in one test to prove
that scope filtering happens before LIMIT, rather than checking a vacuous denial.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlite_vec import serialize_float32

from app.ai import AGENTS, AIError
from test_application import workspace, account, make_case, ORIGIN

MAYA = 'MAYA_PRIVATE_TOKEN_Q7 damaged headphones evidence'
SAM = 'SAM_PRIVATE_TOKEN_R9 damaged keyboard evidence'
UNKNOWN = 'RG-FFFFFFFF'


@pytest.fixture
def scoped_records(workspace):
    app, admin = workspace
    cases = {'demo-maya':make_case(admin), 'demo-sam':make_case(admin,'DEMO-SAM',7500)}
    documents = {}
    for customer, content in [('demo-maya',MAYA),('demo-sam',SAM)]:
        response = admin.post('/api/knowledge',json={'title':content.split()[0],
                              'kind':'customer','customer_id':customer,'content':content})
        assert response.status_code == 200,response.text
        documents[customer] = response.json()['id']
    return app, admin, cases, documents


def assert_scoped(app, results, customer, own_doc=None):
    assert results, 'A blanket empty result is not successful authorized retrieval'
    allowed = {row['id'] for row in app.state.store.all(
        "SELECT id FROM rg_documents WHERE active=1 AND (kind='policy' OR customer_id=?)",(customer,))}
    assert {row['source_id'] for row in results} <= allowed
    if own_doc:
        assert own_doc in {row['source_id'] for row in results}
    for row in results:
        assert {'source_id','title','version','kind','content','chunk_no','distance'} <= row.keys()


@pytest.mark.parametrize('customer,own,foreign', [('demo-maya',MAYA,SAM),('demo-sam',SAM,MAYA)])
def test_records_agent_returns_own_evidence_without_foreign_text_or_metadata(scoped_records,customer,own,foreign):
    app, _, cases, documents = scoped_records
    results = app.state.workflow.records.retrieve(cases[customer],own)
    assert_scoped(app,results,customer,documents[customer])
    assert own in json.dumps(results)
    assert foreign.split()[0] not in json.dumps(results)
    other = 'demo-sam' if customer=='demo-maya' else 'demo-maya'
    assert documents[other] not in json.dumps(results)


def test_filter_precedes_top_k_even_when_foreign_document_is_nearest(scoped_records):
    app, _, _, documents = scoped_records
    store, knowledge, models = app.state.store, app.state.knowledge, app.state.workflow.models
    query = [1.0]+[0.0]*383
    own = [0.9,0.1]+[0.0]*382
    unrelated = [-1.0]+[0.0]*383
    with store.connect() as db:
        db.execute('UPDATE rg_chunks SET embedding=?',(serialize_float32(unrelated),))
        db.execute('UPDATE rg_chunks SET embedding=? WHERE document_id=?',(serialize_float32(own),documents['demo-maya']))
        db.execute('UPDATE rg_chunks SET embedding=? WHERE document_id=?',(serialize_float32(query),documents['demo-sam']))
    with store.connect(vector=True) as db:
        ranked = db.execute('SELECT document_id,vec_distance_cosine(embedding,?) AS distance FROM rg_chunks ORDER BY distance',
                            (serialize_float32(query),)).fetchall()
    assert ranked[0]['document_id']==documents['demo-sam']
    with patch.object(models,'embedding',return_value=[query]):
        results = knowledge.search('damaged item','demo-maya',limit=1)
    assert len(results)==1
    assert results[0]['source_id']==documents['demo-maya']
    assert SAM.split()[0] not in json.dumps(results)


def test_query_cannot_select_a_different_customer(scoped_records):
    app, _, cases, _ = scoped_records
    records, knowledge = app.state.workflow.records, app.state.knowledge
    with patch.object(knowledge,'search',wraps=knowledge.search) as search:
        results = records.retrieve(cases['demo-maya'],'Sam Rivera '+SAM)
    assert search.call_args.args[1]=='demo-maya'
    assert_scoped(app,results,'demo-maya')
    assert SAM.split()[0] not in json.dumps(results)


@pytest.mark.parametrize('case_id', [UNKNOWN,'not-a-case',"RG-12345678' OR 1=1 --",''])
def test_unknown_or_forged_internal_case_never_starts_retrieval(workspace,case_id):
    app, _ = workspace
    with patch.object(app.state.knowledge,'search') as search,patch.object(app.state.workflow.models,'_post') as provider:
        with pytest.raises(AIError,match='No authorized records scope'):
            app.state.workflow.records.retrieve(case_id,'customer records')
    search.assert_not_called()
    provider.assert_not_called()


@pytest.mark.parametrize('case_id,expected', [(UNKNOWN,404),('not-a-case',422),("RG-12345678' OR 1=1 --",422)])
def test_invalid_case_search_api_denies_before_retrieval_or_embeddings(workspace,case_id,expected):
    app, admin = workspace
    with patch.object(app.state.knowledge,'search') as search,patch.object(app.state.workflow.models,'embedding') as embedding:
        response = admin.post('/api/knowledge/search',json={'case_id':case_id,'query':'customer records'})
    assert response.status_code==expected,response.text
    assert 'Maya Chen' not in response.text and 'Sam Rivera' not in response.text
    search.assert_not_called()
    embedding.assert_not_called()


@pytest.mark.parametrize('role,expected',[('anonymous',401),('customer',403)])
def test_nonstaff_search_is_denied_for_own_other_and_unknown_cases(workspace,role,expected):
    app, admin = workspace
    customer, _ = account(app,admin,'customer')
    own = make_case(customer,customer.get('/api/orders').json()[0]['id'])
    other = make_case(admin)
    client = customer if role=='customer' else TestClient(app,base_url=ORIGIN,headers={'Origin':ORIGIN})
    with patch.object(app.state.knowledge,'search') as search,patch.object(app.state.workflow.models,'_post') as provider:
        for cid in (own,other,UNKNOWN):
            result = client.post('/api/knowledge/search',json={'case_id':cid,'query':'refund documents'})
            assert result.status_code==expected,result.text
            assert 'source_id' not in result.text and 'bank_ref' not in result.text
    search.assert_not_called()
    provider.assert_not_called()


@pytest.mark.parametrize('role',['member','supervisor','admin'])
def test_current_staff_policy_allows_search_but_results_remain_case_scoped(scoped_records,role):
    # This deliberately preserves current broad staff case access. It does not
    # claim that human-assignment restrictions have been implemented.
    app, admin, cases, documents = scoped_records
    client = admin if role=='admin' else account(app,admin,role)[0]
    response = client.post('/api/knowledge/search',json={'case_id':cases['demo-maya'],'query':MAYA})
    assert response.status_code==200,response.text
    assert_scoped(app,response.json(),'demo-maya',documents['demo-maya'])
    assert SAM.split()[0] not in response.text


def test_client_cannot_supply_an_alternate_retrieval_scope(scoped_records):
    app, admin, cases, _ = scoped_records
    with patch.object(app.state.knowledge,'search') as search:
        response = admin.post('/api/knowledge/search',json={'case_id':cases['demo-maya'],'query':MAYA,
                              'customer_id':'demo-sam'})
    assert response.status_code==422
    search.assert_not_called()


def test_policy_lifecycle_controls_retrieved_text_not_just_database_flags(workspace):
    app, admin = workspace
    reviewer, _ = account(app,admin,'supervisor')
    knowledge = app.state.knowledge
    def upload(title,content):
        response = admin.post('/api/knowledge',json={'title':title,'kind':'policy','content':content})
        assert response.status_code==200,response.text
        return response.json()['id']
    def retrieved():
        return knowledge.search('refund policy damaged item','demo-maya',limit=50)
    first = upload('Access test policy','POLICY_FIRST_MARKER: damaged items need a verified purchase.')
    rejected = upload('Rejected access policy','POLICY_REJECTED_MARKER: customer support draft policy.')
    assert reviewer.post('/api/knowledge/'+rejected+'/review',json={'action':'reject'}).status_code==200
    pending = retrieved()
    assert pending and first not in {r['source_id'] for r in pending}
    assert 'POLICY_FIRST_MARKER' not in json.dumps(pending)
    assert 'POLICY_REJECTED_MARKER' not in json.dumps(pending)
    assert admin.post('/api/knowledge/'+first+'/review',json={'action':'publish'}).status_code==409
    assert reviewer.post('/api/knowledge/'+first+'/review',json={'action':'publish'}).status_code==200
    published = retrieved()
    assert any(r['source_id']==first and r['version']==1 and 'POLICY_FIRST_MARKER' in r['content'] for r in published)
    second = upload('Access test policy','POLICY_SECOND_MARKER: covered requests need verified order ownership.')
    # A pending replacement must not hide the still-approved version.
    before_review = retrieved()
    assert first in {r['source_id'] for r in before_review}
    assert second not in {r['source_id'] for r in before_review}
    assert reviewer.post('/api/knowledge/'+second+'/review',json={'action':'publish'}).status_code==200
    replaced = retrieved()
    assert any(r['source_id']==second and r['version']==2 for r in replaced)
    assert first not in {r['source_id'] for r in replaced}
    assert 'POLICY_FIRST_MARKER' not in json.dumps(replaced)
    assert reviewer.post('/api/knowledge/'+first+'/review',json={'action':'rollback'}).status_code==200
    rolled_back = retrieved()
    assert first in {r['source_id'] for r in rolled_back}
    assert second not in {r['source_id'] for r in rolled_back}
    assert 'POLICY_SECOND_MARKER' not in json.dumps(rolled_back)
    assert rejected not in {r['source_id'] for r in rolled_back}
    assert 'POLICY_REJECTED_MARKER' not in json.dumps(rolled_back)


def test_customer_document_supersession_does_not_replace_another_customers_same_title(workspace):
    app, _ = workspace
    knowledge = app.state.knowledge
    first = knowledge.add('Shared evidence','MAYA_OLD_MARKER original damage report.','customer','demo-maya','system')
    other = knowledge.add('Shared evidence','SAM_CURRENT_MARKER keyboard damage report.','customer','demo-sam','system')
    latest = knowledge.add('Shared evidence','MAYA_CURRENT_MARKER corrected damage report.','customer','demo-maya','system')
    maya = knowledge.search('damage report','demo-maya',limit=50)
    sam = knowledge.search('damage report','demo-sam',limit=50)
    assert latest in {r['source_id'] for r in maya} and first not in {r['source_id'] for r in maya}
    assert 'MAYA_OLD_MARKER' not in json.dumps(maya)
    assert 'SAM_CURRENT_MARKER' not in json.dumps(maya)
    assert other in {r['source_id'] for r in sam}
    assert 'MAYA_CURRENT_MARKER' not in json.dumps(sam)
    assert app.state.store.one('SELECT active FROM rg_documents WHERE id=?',(other,))['active']==1


def test_lazy_embedding_does_not_send_another_customers_pending_content(scoped_records):
    app, _, _, _ = scoped_records
    knowledge, models, store = app.state.knowledge, app.state.workflow.models, app.state.store
    foreign = knowledge.add('Deferred Sam evidence','SAM_DEFERRED_SECRET_81 private keyboard history.',
                            'customer','demo-sam','system',index=False)
    store.execute("UPDATE rg_profiles SET notes=? WHERE id='demo-sam'",('SAM_NOTES_SECRET_82 confidential notes.',))
    own = knowledge.add('Deferred Maya evidence','MAYA_DEFERRED_MARKER_83 headphones damage.',
                        'customer','demo-maya','system',index=False)
    sent = []
    original_embedding = models.embedding
    def capture(texts):
        sent.extend(texts)
        return original_embedding(texts)
    with patch.object(models,'embedding',side_effect=capture):
        results = knowledge.search('headphones damage','demo-maya',limit=50)
    assert_scoped(app,results,'demo-maya',own)
    assert 'MAYA_DEFERRED_MARKER_83' in json.dumps(sent)
    assert 'SAM_DEFERRED_SECRET_81' not in json.dumps(sent)
    assert 'SAM_NOTES_SECRET_82' not in json.dumps(sent)
    assert not store.one('SELECT id FROM rg_chunks WHERE document_id=?',(foreign,))


def test_interleaved_searches_do_not_share_customer_scope(scoped_records):
    app, _, _, documents = scoped_records
    knowledge = app.state.knowledge
    tasks = [('demo-maya',MAYA,SAM),('demo-sam',SAM,MAYA)]*3
    def search(task):
        customer, query, forbidden = task
        rows = knowledge.search(query,customer,limit=50)
        assert_scoped(app,rows,customer,documents[customer])
        assert forbidden.split()[0] not in json.dumps(rows)
        return customer
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(search,tasks))==[task[0] for task in tasks]


def test_workflow_provider_payloads_and_retrieval_traces_keep_customer_scope(scoped_records):
    app, admin, cases, documents = scoped_records
    models = app.state.workflow.models
    sent = []
    def provider(path,payload):
        sent.append(payload)
        if path=='/embeddings':
            return {'data':[{'index':i,'embedding':[1.0]*384} for i in range(len(payload['input']))]}
        replies = {'Plan':{'steps':AGENTS,'summary':'Fixed plan'},
                   'Recommendation':{'decision':'approve','rationale':'Verified covered purchase','source_ids':[]},
                   'Draft':{'subject':'Refund update','body':'Your request was processed.'},
                   'Summary':{'summary':'Recorded refund execution.'}}
        return {'output':[{'type':'message','content':[{'type':'output_text',
                'text':json.dumps(replies[payload['text']['format']['name']])}]}]}
    with patch.object(models.settings,'provider','openai'),patch.object(models,'_post',side_effect=provider):
        result = admin.post('/api/cases/'+cases['demo-maya']+'/run',json={})
    assert result.status_code==200 and result.json()['status']=='processed',result.text
    assert MAYA.split()[0] in json.dumps(sent)
    assert SAM.split()[0] not in json.dumps(sent)
    assert documents['demo-sam'] not in json.dumps(sent)
    traces = app.state.store.all("SELECT result FROM rg_traces WHERE case_id=? AND operation='retrieve'",(cases['demo-maya'],))
    assert len(traces)==1
    sources = json.loads(traces[0]['result'])['sources']
    assert_scoped(app,sources,'demo-maya',documents['demo-maya'])
    assert SAM.split()[0] not in json.dumps(sources)
