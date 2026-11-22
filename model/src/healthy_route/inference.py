"""Portable inference without participant records or patient-specific initial state."""
from pathlib import Path
import hashlib,json
import numpy as np
import torch
from .state_cvae_model import StateCVAE

ASSETS=Path(__file__).parent/'assets'

def load_model():
    manifest=json.loads((ASSETS/'manifest.json').read_text())
    for name in ('state_cvae.pt','scaler.json'):
        if hashlib.sha256((ASSETS/name).read_bytes()).hexdigest()!=manifest['files'][name]:
            raise ValueError('Inference asset checksum mismatch: '+name)
    scaler=json.loads((ASSETS/'scaler.json').read_text())
    mean=np.asarray(scaler['mean']);scale=np.asarray(scaler['scale'])
    if mean.shape!=(9,) or scale.shape!=(9,) or not np.isfinite(mean).all() or not np.isfinite(scale).all() or (scale<=0).any():
        raise ValueError('Invalid model normalization')
    model=StateCVAE();model.load_state_dict(torch.load(ASSETS/'state_cvae.pt',map_location='cpu',weights_only=True)['state_dict']);model.eval()
    return model,mean,scale,manifest

def predict(features,initial_breathing_bpm,particles,seed,checkpoint=lambda:None):
    model,mean,scale,manifest=load_model()
    rows=np.asarray(features,dtype=float)
    if rows.ndim!=2 or rows.shape[1]!=8 or not np.isfinite(rows).all():raise ValueError('Expected finite N x 8 features')
    h,last=model.initial(particles)
    last[:]=(initial_breathing_bpm-mean[8])/scale[8]
    rng=np.random.default_rng(seed);values=[np.full(particles,initial_breathing_bpm)]
    with torch.no_grad():
        for row in rows:
            checkpoint()
            x=torch.tensor((row-mean[:8])/scale[:8],dtype=torch.float32)[None].repeat(particles,1)
            eps=torch.tensor(rng.normal(size=(particles,4)),dtype=torch.float32)
            _,_,(h,last),_=model.step(x,(h,last),eps)
            br=last[:,0].numpy()*scale[8]+mean[8]
            if not np.isfinite(br).all() or (br<=0).any():raise ValueError('Nonphysical breathing prediction; inspect out-of-domain inputs')
            values.append(br.copy())
    values=np.asarray(values)
    return values.mean(1),values.std(1),manifest
