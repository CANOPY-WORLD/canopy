"""One lifecycle for all methods, isolated execution and explicit asset retention."""
from datetime import datetime, timezone
import importlib.util
import importlib.metadata
import json
import platform
from pathlib import Path
import shutil
import uuid
from jsonschema import Draft202012Validator
from canopy._io import read, write, check, digest
from canopy.scenario.store import load as scenario_load
from canopy.assets.store import load as asset_load, import_run
from canopy.models.registry import describe, implementation
from canopy.models.interface import Context
from common.provenance import snapshot_sources
from common.contract import validate as validate_payload


def prepare_request(storage, request):
    request=json.loads(json.dumps(request,allow_nan=False));check(request,'request')
    scenario=scenario_load(storage,request['scenario_id'])
    spec=describe(request['model_id'],request['method_id'])
    if request['method_version']!=spec['version']:raise ValueError('Method version mismatch')
    if set(request['inputs'])!=set(spec['inputs']):raise ValueError('Input ports differ from method contract')
    for key,prop in spec['parameters']['properties'].items():
        if key not in request['parameters'] and 'default' in prop:request['parameters'][key]=prop['default']
    Draft202012Validator(spec['parameters']).validate(request['parameters'])
    inputs={}
    for name,reference in request['inputs'].items():
        inputs[name]=asset_load(storage,request['scenario_id'],reference)
        asset,manifest,_=inputs[name];port=spec['inputs'][name]
        if asset['kind']!=port['kind']:raise ValueError(f'{name}: wrong asset kind')
        kinds={x['kind'] for x in manifest['layers'] if x['id'] in asset['payload']['layers']}
        if not set(port['required_layers'])<=kinds:raise ValueError(f'{name}: required layer type missing')
    for dependency in spec['dependencies']:
        if importlib.util.find_spec(dependency) is None:raise ValueError(f'Missing {dependency}; install the physics optional dependencies in the chosen environment')
    if 'torch' in spec['dependencies']:
        import torch
        if request['execution'].get('device','cpu')=='cuda' and not torch.cuda.is_available():raise ValueError('CUDA requested but unavailable')
    context=Context(storage,scenario,Path('.'),'',inputs,lambda *a,**k:None,lambda:False)
    implementation(spec).validate(request,context)
    return request,spec,scenario,inputs


def run(storage,request,*,retain=True):
    request,spec,scenario,inputs=prepare_request(storage,request)
    rid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:10]
    workspace=storage.scratch(scenario['scenario_id'],request['model_id'],rid);workspace.mkdir(parents=True,exist_ok=False)
    state={'schema_version':'2.0.0','run_id':rid,'scenario_id':scenario['scenario_id'],'model_id':spec['model_id'],'method_id':spec['method_id'],'status':'preparing','assets':[]}
    write(workspace/'request.json',request);write(workspace/'run.json',state)
    def emit(event,**fields):
        with (workspace/'events.jsonl').open('a') as stream:stream.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'event':event,**fields},allow_nan=False)+'\n')
    context=Context(storage,scenario,workspace,rid,inputs,emit,lambda:(workspace/'cancel.request').exists())
    context.request=request;context.created_at=datetime.now(timezone.utc).isoformat()
    try:
        revision=snapshot_sources(storage.root,workspace/'source_snapshot.tar.gz')
        context.provenance={'code_revision':revision,'dirty':True,'parameters':request,'inputs':[{'id':name,'sha256':digest(value[2])} for name,value in inputs.items()]}
        write(workspace/'environment.json',{'python':platform.python_version(),'platform':platform.platform(),'method_version':spec['version'],'dependencies':{name:importlib.metadata.version(name) for name in ['numpy','jsonschema',*spec['dependencies']]},'execution':request['execution']})
        method=implementation(spec)
        if 'torch' in spec['dependencies']:
            import torch
            previous_threads=torch.get_num_threads();torch.set_num_threads(request['execution'].get('threads',1))
        else:previous_threads=None
        try:
            context.checkpoint();prepared=method.prepare(request,context)
            state['status']='running';write(workspace/'run.json',state);emit('running')
            result=method.execute(prepared,context);context.checkpoint()
            state['status']='exporting';write(workspace/'run.json',state)
            payload=method.export(result,context)
        finally:
            if previous_threads is not None:torch.set_num_threads(previous_threads)
        manifest=read(payload/'manifest.json')
        kinds={x['kind'] for x in manifest['layers']}
        if not set(spec['outputs'])<=kinds:raise ValueError('Output types differ from method declaration')
        write(workspace/'diagnostics.json',result['diagnostics'])
        for name,media in [('source_snapshot.tar.gz','application/gzip'),('request.json','application/json'),('environment.json','application/json'),('diagnostics.json','application/json'),('events.jsonl','application/x-ndjson')]:
            target=payload/'provenance'/name;target.parent.mkdir(exist_ok=True)
            shutil.copy2(workspace/name,target)
            manifest['artifacts'].append({'id':'source_snapshot' if name=='source_snapshot.tar.gz' else name.replace('.','_'),'asset':str(target.relative_to(payload)),'sha256':digest(target),'media_type':media})
        write(payload/'manifest.json',manifest);validate_payload(payload/'manifest.json');context.checkpoint()
        if retain:state['assets']=import_run(storage,scenario['scenario_id'],payload,derived_from=request['inputs'].values(),expected_kind=spec['category'])
        state.update(status='complete',payload=str(payload),diagnostics=result['diagnostics']);emit('complete',assets=state['assets'])
    except (KeyboardInterrupt,InterruptedError) as exc:
        state.update(status='cancelled',error=str(exc));emit('cancelled');raise
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}');emit('failed',error=state['error']);raise
    finally:write(workspace/'run.json',state)
    return state
