"""Explicit execution of a pinned, private healthy-route input bundle."""
import shutil
import numpy as np
from canopy._io import read, write, relative, digest
from .interface import Method
from .methods import base

class HealthyRoute(Method):
    def validate(self, request, context):
        if request['execution'].get('device','cpu') != 'cpu':
            raise ValueError('Healthy route currently supports CPU execution only')
        _, manifest, path = context.inputs['bundle']
        entries={a['id']:a for a in manifest.get('artifacts',[])}
        if 'healthy_route_bundle' not in entries:
            raise ValueError('Input must declare a healthy_route_bundle artifact')
        meta=read(relative(path.parent,entries['healthy_route_bundle']['asset']))
        if meta.get('format') != 'healthy-route-private-bundle-v1':
            raise ValueError('Unsupported healthy-route input format')
        if meta.get('scenario_id') != context.scenario['scenario_id'] or meta.get('spatial') != context.scenario['spatial']:
            raise ValueError('Bundle coordinate/Scenario identity mismatch')
        declared={a['asset'] for a in manifest['artifacts']}
        for name in meta['files']:
            if name not in declared: raise ValueError('Undeclared bundle file')
            if digest(relative(path.parent,name)) != meta['files'][name]:
                raise ValueError('Bundle checksum mismatch: '+name)
        required={'pedestrian/generated/network.json','pedestrian/scenario.json',
                  'pedestrian/private/breathing_model/state_cvae.pt'}
        if not required <= set(meta['files']): raise ValueError('Incomplete private bundle')
        profile=read(relative(path.parent,'pedestrian/scenario.json'))
        if profile.get('experiment_id') != 'healthy_route_extended_replay_v2':
            raise ValueError('Explicit extended-replay experiment profile required')
        p=request['parameters']
        if p['departure_s']+p['max_minutes']*60>profile['max_journey_horizon_s']:
            raise ValueError('Request exceeds experiment horizon')
        network=read(relative(path.parent,'pedestrian/generated/network.json'))
        if p['origin'] not in network['nodes'] or p['goal'] not in network['nodes']:
            raise ValueError('Endpoints must be declared network node IDs')
        return meta

    def prepare(self, request, context):
        meta=self.validate(request,context)
        root=context.inputs['bundle'][2].parent
        return root, request['parameters']

    def execute(self, prepared, context):
        from healthy_route.canopy_planner import CanopyPlanner
        root,parameters=prepared
        context.checkpoint(); context.emit('initializing')
        planner=CanopyPlanner(root,cache_root=context.workspace/'traffic-cache')
        context.checkpoint(); context.emit('planning')
        result=planner.plan(parameters)
        context.checkpoint()
        return {'route':result,'diagnostics':{'quality':'exploratory_conditional_scenario',
            'experiment_id':'healthy_route_extended_replay_v2',
            'limitations':'Bounded search; repeated environmental/traffic scenario; uncalibrated running physiology; not clinical or road-safety validation'}}

    def export(self,result,context):
        folder=context.workspace/'payload';folder.mkdir()
        route=result['route'];selected=route['routes'][1]
        times=[float(s['seconds']) for s in selected['profile']]
        if not times or not np.isfinite(times).all() or any(b<a for a,b in zip(times,times[1:])):
            raise ValueError('Route samples must be finite and ordered')
        # Adjacent events may share a boundary; preserve full route samples in the artifact.
        times=sorted(set(times))
        write(folder/'route.json',route)
        write(folder/'elapsed.json',{'labels':['journey_elapsed'],'values':[[t] for t in times]})
        m=base(context,times)
        m['layers']=[{'id':'journey_elapsed','kind':'time_series','format':'json','asset':'elapsed.json',
            'sampling':'linear','field':{'name':'journey_elapsed','unit':'s'},
            'display':{'widget':'time_series','capabilities':['pick']}}]
        m['artifacts']=[{'id':'healthy_route_result','asset':'route.json','sha256':digest(folder/'route.json'),'media_type':'application/json'}]
        # Full research routes use the same standard layers as portable inference.
        if selected.get('timeline'):
            positions=[]
            for t in times:
                event=next((e for e in selected['timeline'] if e['start']<=t<e['end']),selected['timeline'][-1])
                points=np.asarray(event['points'],dtype=float)
                if event['kind']=='Waiting':point=points[0]
                else:
                    f=np.clip((t-event['start'])/(event['end']-event['start']),0,1)
                    d=np.asarray(event['distance']);point=np.array([np.interp(f*d[-1],d,points[:,i]) for i in range(3)])
                positions.append([point.tolist()])
            write(folder/'trajectory.json',{'ids':['selected_route'],'positions':positions})
            m['layers'].append({'id':'trajectory','kind':'trajectories','format':'json','asset':'trajectory.json','sampling':'linear','display':{'widget':'trajectories','capabilities':['pick','opacity']}})
            for key,unit in [('temperature','degC'),('pollution','ug/m3'),('sunlight','W/m2'),('thermal_proxy','degC')]:
                rows=selected['profile']
                if not all(isinstance(row.get(key),(int,float)) and np.isfinite(row[key]) for row in rows):continue
                values=np.interp(times,[row['seconds'] for row in rows],[row[key] for row in rows])
                write(folder/(key+'.json'),{'labels':[key],'values':[[float(v)] for v in values]})
                m['layers'].append({'id':key,'kind':'time_series','format':'json','asset':key+'.json','sampling':'linear','field':{'name':key,'unit':unit},'display':{'widget':'time_series','capabilities':['pick']}})
            rows=selected.get('breathing_profile',[])
            if rows:
                values=[next((row['breathing'] for row in reversed(rows) if row['seconds']<=t),rows[0]['breathing']) for t in times]
                write(folder/'breathing.json',{'labels':['breathing'],'values':[[float(v)] for v in values]})
                m['layers'].append({'id':'breathing','kind':'time_series','format':'json','asset':'breathing.json','sampling':'step','field':{'name':'breathing','unit':'breaths/min'},'display':{'widget':'time_series','capabilities':['pick']}})
        write(folder/'manifest.json',m)
        return folder
