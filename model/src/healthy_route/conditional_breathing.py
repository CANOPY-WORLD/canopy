"""Conditional five-minute CVAE transitions along an already selected walk."""
import numpy as np
import pandas as pd


class BreathingCosts:
    def __init__(self, departure, values, config, runtime, baseline, neutral=False):
        self.departure,self.values,self.config,self.neutral=departure,values,config,neutral
        self.runtime, self.baseline = runtime, baseline
        self.offset = float(config['breathing_history_offset_s']) + departure
        knot = int(self.offset // 300) * 300
        if knot not in runtime.states:
            raise ValueError('Departure outside retained participant-history coverage')
        self.initial = runtime.states[knot]
        if self.offset > knot:
            self.initial = runtime.advance(self.initial, runtime.features(runtime.start + pd.Timedelta(seconds=self.offset)), self.offset-knot)
        self.trace = None
        self.feature_cache = {}

    def density(self,state,elapsed):
        b=self.baseline[min(len(self.baseline)-1,int((self.offset+elapsed)//1800))]
        br=self.runtime.br(state)
        outside=np.maximum(np.maximum(b['q10']-br,br-b['q90']),0)/b['scale']
        return float(outside.mean()+.5*outside.std(ddof=1))

    def prediction(self,state,seconds):
        values=self.runtime.br(state)
        return dict(seconds=float(seconds),breathing=float(values.mean()),latent_sd=float(values.std(ddof=1)),updates=state.updates-self.initial.updates)

    def transition(self,state,elapsed,duration,temperature,at):
        # Absolute two-second knots plus model boundaries prevent a street split
        # from resetting either the exposure clock or five-minute model phase.
        t=0.;parts=np.zeros(3);exposure=0.
        while t<duration-1e-8:
            now=elapsed+t
            take=min(duration-t,2.-(now%2),300.-state.phase)
            if take<1e-8:take=min(duration-t,2.,300.-state.phase)
            mid=now+take/2;point=at(t+take/2)
            sampler_pm=getattr(self,'pollution_sampler',None)
            raw_pm=sampler_pm(point,self.departure+mid) if sampler_pm else None
            missing_pollution=raw_pm is None
            pm=float(self.runtime.mean[0]) if missing_pollution else raw_pm
            sampler=getattr(self,'temperature_sampler',None)
            missing_temperature=False
            if sampler is not None:
                native=sampler(point,self.departure+mid)
                missing_temperature=native is None
                temperature=float(self.runtime.mean[1]) if missing_temperature else native
            thermal_sampler=getattr(self,'thermal_sampler',None)
            thermal=thermal_sampler(point,self.departure+mid) if thermal_sampler else temperature
            if thermal is None:thermal=temperature;missing_temperature=True
            rho=1. if self.neutral else 1.+.5*pm/10.+.25*(max(thermal-26.,18.-thermal,0.)/5)**2
            # Missing data must not look like a cooler, healthier shortcut.
            if (missing_temperature or missing_pollution) and not self.neutral:rho+=self.config.get('missing_temperature_penalty',3.)
            parts[0]+=take*rho
            if not self.neutral:parts[2]+=take*self.density(state,now)
            exposure+=pm*take
            minute=int((self.offset+mid)//60)
            if minute not in self.feature_cache:
                self.feature_cache[minute]=self.runtime.features(self.runtime.start+pd.Timedelta(seconds=minute*60))
            x=self.feature_cache[minute].copy();x[0]=pm;x[1]=temperature
            updates=state.updates
            state=self.runtime.advance(state,x,take);t+=take
            if self.trace is not None and state.updates!=updates:
                self.trace.append(self.prediction(state,elapsed+t))
        return state,parts,exposure
