"""One viewer template, declarative per-scenario selection and camera."""
from canopy.scenario.store import load as load_scenario, data_root, lock
from canopy.assets.store import load as load_asset
from canopy._io import write, check


def select(storage,scenario,references,preset='engineering'):
    selections=[]
    for reference in references:
        asset,manifest,_=load_asset(storage,scenario,reference)
        selections.extend({'asset':reference,'layer':id,'visible':True} for id in asset['payload']['layers'])
    with lock(storage,scenario):
        data=load_scenario(storage,scenario)
        data['visualization'].update(template='standard',preset=preset,layers=selections)
        check(data,'scenario');write(storage.metadata(scenario)/'scenario.json',data)
    return data['visualization']


def describe(storage,scenario):
    data=load_scenario(storage,scenario);profile=data['visualization'];runs={};selections=[]
    for choice in profile['layers']:
        asset,manifest,path=load_asset(storage,scenario,choice['asset'],verify=False)
        if choice['layer'] not in asset['payload']['layers']:raise ValueError('View layer does not belong to asset')
        key=manifest['run_id']
        url='/project/'+scenario+'/'+str(path.relative_to(data_root(storage,scenario)))
        if key in runs and runs[key]['url']!=url:raise ValueError('Ambiguous run identity in view')
        runs[key]={'url':url}
        selections.append({'run_id':key,'layer_id':choice['layer'],'visible':choice.get('visible',True)})
    return {'scenario_id':scenario,'title':data['title'],'spatial':data['spatial'],'profile':profile,'runs':list(runs.values()),'layers':selections}
