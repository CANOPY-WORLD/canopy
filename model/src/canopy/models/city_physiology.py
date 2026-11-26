"""Conditional physiology using the packaged model on current city fields."""
from canopy._io import read, write, digest
from canopy.assets.store import load
from .city_exposure import CityExposure
from .interface import Method


class CityPhysiology(Method):
    def validate(self, request, context):
        if request['execution'].get('device','cpu')!='cpu':raise ValueError('CPU execution required')
        city=context.inputs['city'][2].parent
        meta=read(city/'city-inputs.json')
        exposure=read(context.inputs['exposure'][2].parent/'recording.json')
        if meta.get('format')!='canopy-city-alignment-v1' or exposure['inputs']['city']!=request['inputs']['city']:
            raise ValueError('Exposure and current city must use the same exact input Asset')
        root=context.inputs['physiology'][2].parent
        required=['physiology.json']
        declared={a['asset'] for a in context.inputs['physiology'][1]['artifacts']}
        if not all(name in declared for name in required):
            raise ValueError('Missing declared physiology input profile')
        from healthy_route.conditional_runtime import read_profile
        read_profile(root)
        from healthy_route.inference import load_model
        if read(root/'model-identity.json')!=load_model()[3]:raise ValueError('Physiology Asset model identity differs from packaged weights')
        if request['parameters']['followup_until_elapsed_s']+exposure['departure_s']>600:
            raise ValueError('Follow-up exceeds the current field coverage')
        return city,root,exposure,meta

    def prepare(self,request,context):
        return *self.validate(request,context),request['parameters']

    def execute(self,prepared,context):
        from healthy_route.city_physiology import EstimatedCityFields,evaluate
        from healthy_route.conditional_runtime import Runtime
        city,root,exposure,meta,policy=prepared
        folder=root
        context.checkpoint();runtime=Runtime(folder,seed=42,particles=16,checkpoint=context.checkpoint)
        result=evaluate(exposure,EstimatedCityFields(city,meta['fields']),runtime,runtime.baseline,policy,context.checkpoint)
        result['physiology_audit']['inference_input_sha256']={p.name:digest(p) for p in folder.iterdir() if p.is_file()}
        result['physiology_inputs']=context.request['inputs']
        result['physiology_input_kind']=runtime.input_kind
        result['physiology_audit']['packaged_model']=runtime.model_manifest
        result['physiology_note']=('Synthetic covariate template and assumed reference; no participant data. ' if runtime.input_kind=='synthetic' else 'Locally supplied authorized history; outputs remain private. ')+result['physiology_note']
        context.emit('progress',completed=len(result['samples']),total=len(result['samples']))
        return {'recording':result,'diagnostics':{'samples':len(result['samples']),**result['physiology_audit'],
            'scientific_status':'conditional model inference; no accuracy or clinical validation'}}

    def export(self,result,context):
        folder=CityExposure.export(self,result,context);m=read(folder/'manifest.json');rows=result['recording']['samples']
        for key,unit in [('pollution_proxy','ug/m3'),('temperature_estimate','degC'),('sunlight_estimate','W/m2'),('thermal_proxy','degC'),('breathing','breaths/min'),('latent_sd','breaths/min'),('health_score','1')]:
            if any(row[key] is None for row in rows):continue
            write(folder/(key+'.json'),{'labels':[key],'values':[[r[key]] for r in rows]})
            m['layers'].append({'id':key,'kind':'time_series','format':'json','asset':key+'.json','sampling':'step',
                'field':{'name':key,'unit':unit},'display':{'widget':'time_series','capabilities':['pick']}})
        write(folder/'manifest.json',m);return folder
