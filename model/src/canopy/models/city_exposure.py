"""Evaluate an existing recorded route against an exact city presentation snapshot."""
from canopy._io import read, write, digest
from .interface import Method
from .methods import base
from healthy_route.city_alignment import Terrain, CityFields, align_recording


class CityExposure(Method):
    def validate(self, request, context):
        root=context.inputs['city'][2].parent
        meta=read(root/'city-inputs.json')
        if meta['format']!='canopy-city-alignment-v1':
            raise ValueError('Explicit pinned city input bundle required')
        declared={a['asset'] for a in context.inputs['city'][1]['artifacts']}
        for name,sha in meta['files'].items():
            from canopy._io import relative
            if name not in declared or digest(relative(root,name))!=sha:
                raise ValueError('City alignment input checksum mismatch: '+name)
        if context.inputs['geometry'][2] != context.inputs['city'][2]:
            raise ValueError('Geometry and fields must reference the same verified city snapshot')
        return meta

    def prepare(self, request, context):
        meta=self.validate(request,context)
        return context.inputs['city'][2].parent, context.inputs['recording'][2].parent,meta

    def execute(self, prepared, context):
        city,recorded,meta=prepared
        terrain=Terrain(read(city/'scenes/imperial_corridor_8km/context/terrain/terrain.json')['terrain'])
        result=align_recording(read(recorded/'route.json'),read(city/'network.json'),terrain,CityFields(city,meta['fields']),context.checkpoint)
        result['alignment']=meta['alignment'];result['inputs']=context.request['inputs']
        context.emit('progress',completed=len(result['samples']),total=len(result['samples']))
        return {'recording':result,'diagnostics':{'samples':len(result['samples']),'max_xy_residual_m':max(p['xy_residual_m'] for p in result['control_points']),
            'max_scene_z_reconstruction_residual_m':max(abs(p['reconstructed_scene_z_residual_m']) for p in result['control_points']),
            'physiological_validation':'not performed; physiology unavailable'}}

    def export(self,result,context):
        folder=context.workspace/'payload';folder.mkdir()
        r=result['recording'];rows=r['samples'];m=base(context,[s['world_seconds'] for s in rows])
        write(folder/'recording.json',r)
        write(folder/'trajectory.json',{'ids':['selected_walk' if r.get('route_selection') else 'recorded_route'],'positions':[[s['enu_m']] for s in rows]})
        m['layers']=[{'id':'trajectory','kind':'trajectories','format':'json','asset':'trajectory.json','sampling':'linear','display':{'widget':'trajectories','capabilities':['pick','opacity']}}]
        # Protocol time-series JSON has no missing-value representation. Retain
        # partial series with explicit nulls in recording.json; do not zero-fill.
        for key,unit in [('pmx','ug/m3'),('temperature','degC'),('sunlight','W/m2'),('world_seconds','s')]:
            if any(s[key] is None for s in rows):continue
            write(folder/(key+'.json'),{'labels':[key],'values':[[s[key]] for s in rows]})
            m['layers'].append({'id':key,'kind':'time_series','format':'json','asset':key+'.json','sampling':'linear','field':{'name':'traffic_exhaust_PMx_increment' if key=='pmx' else key,'unit':unit},'display':{'widget':'time_series','capabilities':['pick']}})
        m['artifacts']=[{'id':'city_recording','asset':'recording.json','sha256':digest(folder/'recording.json'),'media_type':'application/json'}]
        write(folder/'manifest.json',m);return folder
