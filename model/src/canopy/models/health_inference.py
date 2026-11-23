"""Public-asset breathing inference with standard scientific-viewer layers."""
import numpy as np
from canopy._io import write,digest
from .interface import Method
from .methods import base

class HealthInference(Method):
    def validate(self,request,context):
        from healthy_route.inference import load_model
        p=request['parameters'];n=len(p['features'])
        if request['execution'].get('device','cpu')!='cpu':raise ValueError('CPU only')
        if len(p['positions_m'])!=n+1 or len(p['irradiance_w_m2'])!=n+1:raise ValueError('Positions and irradiance require N+1 boundary samples')
        rows=np.asarray(p['features'])
        if not np.isfinite(rows).all() or (rows[:,0]<0).any() or ((rows[:,2]<0)|(rows[:,2]>100)).any():raise ValueError('Invalid pollution or humidity')
        lo=np.asarray(context.scenario['spatial']['bounds_m']['min']);hi=np.asarray(context.scenario['spatial']['bounds_m']['max'])
        positions=np.asarray(p['positions_m'])
        if not np.isfinite(positions).all() or (positions<lo).any() or (positions>hi).any():raise ValueError('Trajectory outside Scenario bounds')
        if p['reference_upper_bpm']<=p['reference_lower_bpm']:raise ValueError('Reference upper must exceed lower')
        load_model()
    def prepare(self,request,context):return request['parameters']
    def execute(self,p,context):
        from healthy_route.inference import predict
        mean,sd,assets=predict(p['features'],p['initial_breathing_bpm'],p['particles'],p['seed'],context.checkpoint)
        rows=np.asarray(p['features']);rows=np.vstack([rows,rows[-1]])
        air=rows[:,1];pm=rows[:,0];solar=np.asarray(p['irradiance_w_m2'])
        proxy=air+p['solar_warming_c_per_800']*np.clip(solar/800,0,1.5)
        thermal=np.maximum(np.maximum(18-proxy,proxy-26),0)/8
        breathing=1.5*np.maximum(np.maximum(p['reference_lower_bpm']-mean,mean-p['reference_upper_bpm']),0)/p['reference_scale_bpm']
        score=100*np.exp(-np.log(100/90)*(.35*(pm/15)**2+.15*thermal**2+.50*breathing**2))
        context.emit('progress',completed=len(p['features']),total=len(p['features']))
        return {'times':(np.arange(len(mean))*300).tolist(),'positions':p['positions_m'],
            'fields':{'breathing':(mean,'breaths/min'),'latent_spread':(sd,'breaths/min'),'air_temperature':(air,'degC'),'pollution':(pm,'ug/m3'),'irradiance':(solar,'W/m2'),'thermal_proxy':(proxy,'degC'),'experimental_health_score':(score,'1')},
            'diagnostics':{'initialization':'explicit cold start; zero recurrent memory; not participant replay','input_label':p['input_label'],'inference_assets':assets,'reference':'explicit illustrative reference parameters, not personal baseline','limitations':'Research predictions; latent spread is not total calibrated uncertainty; thermal and health score are heuristic; supplied route is evaluated, not optimized'}}
    def export(self,result,context):
        folder=context.workspace/'payload';folder.mkdir();m=base(context,result['times'])
        for name,(values,unit) in result['fields'].items():
            write(folder/(name+'.json'),{'labels':[name],'values':[[float(v)] for v in values]})
            m['layers'].append({'id':name,'kind':'time_series','format':'json','asset':name+'.json','sampling':'step','field':{'name':name,'unit':unit},'display':{'widget':'time_series','capabilities':['pick']}})
        write(folder/'trajectory.json',{'ids':['supplied_route'],'positions':[[p] for p in result['positions']]})
        m['layers'].append({'id':'trajectory','kind':'trajectories','format':'json','asset':'trajectory.json','sampling':'linear','display':{'widget':'trajectories','capabilities':['pick','opacity']}})
        write(folder/'manifest.json',m);return folder
