"""Conservative positive finite-volume tracer on a uniform ENU Cartesian grid.

Face velocities are explicit, reconstructed inputs are never labelled native MAC.
Open sides/top have zero incremental concentration; bottom/solid faces are sealed.
"""
import math
import torch


class TransientTracer:
    def __init__(self, velocity, fluid, cell_m, diffusivity, device='cpu'):
        if not math.isfinite(cell_m) or cell_m <= 0 or not math.isfinite(diffusivity) or diffusivity < 0:
            raise ValueError('Invalid spacing/diffusivity')
        self.h, self.k = float(cell_m), float(diffusivity)
        self.fluid = torch.as_tensor(fluid, dtype=torch.bool, device=device)
        u = torch.as_tensor(velocity, dtype=torch.float32, device=device)
        if u.shape != (3, *self.fluid.shape) or not torch.isfinite(u).all():
            raise ValueError('Expected finite ENU CZYX velocity matching fluid')
        self.faces, self.masks = [], []
        # Array axes z,y,x correspond to velocity components up,north,east.
        for axis, component in enumerate((2, 1, 0)):
            shape = list(self.fluid.shape); shape[axis] += 1
            f = torch.zeros(shape, device=device); m = torch.zeros(shape, dtype=torch.bool, device=device)
            left, right, middle = self.pair(axis)
            m[middle] = self.fluid[left] & self.fluid[right]
            f[middle] = .5 * (u[component][left] + u[component][right]) * m[middle]
            for end in (0, -1):
                if axis == 0 and end == 0: continue
                s = self.edge(axis, end)
                m[s] = self.fluid[s]; f[s] = u[component][s] * m[s]
            self.faces.append(f); self.masks.append(m)
        self.c = torch.zeros_like(self.fluid, dtype=torch.float32)
        self.emitted_ug = self.outflow_ug = 0.
        self.steps = 0
        self._set_dt()

    @staticmethod
    def edge(axis, end):
        s = [slice(None)] * 3; s[axis] = end; return tuple(s)

    @staticmethod
    def pair(axis):
        a, b, m = [[slice(None)] * 3 for _ in range(3)]
        a[axis] = slice(None, -1); b[axis] = slice(1, None); m[axis] = slice(1, -1)
        return tuple(a), tuple(b), tuple(m)

    def divergence(self, faces):
        out = torch.zeros_like(self.c)
        for axis, f in enumerate(faces):
            a,b,_ = self.pair(axis); out += (f[b]-f[a])/self.h
        return out

    def gradient(self, p):
        result = []
        for axis, mask in enumerate(self.masks):
            g = torch.zeros_like(self.faces[axis]); a,b,m = self.pair(axis)
            g[m] = (p[b]-p[a])/self.h * mask[m]
            for end, sign in ((0,1),(-1,-1)):
                s=self.edge(axis,end);g[s]=sign*2*p[s]/self.h*mask[s]
            result.append(g)
        return result

    def project(self, tolerance=1e-4, max_iterations=2000, checkpoint=lambda:None, progress=lambda **kw:None):
        """Pressure projection of reconstructed faces, open boundary p=0.

        This enforces discrete incompressibility, not validation of the input wind.
        """
        rhs=-self.divergence(self.faces); initial=float(torch.linalg.vector_norm(rhs))
        if initial == 0: return {'iterations':0,'relative_residual':0.}
        p=torch.zeros_like(rhs); r=rhs.clone()
        diagonal=torch.zeros_like(rhs)
        for axis,mask in enumerate(self.masks):
            a,b,m=self.pair(axis);diagonal[a]+=mask[m];diagonal[b]+=mask[m]
            for end in (0,-1):
                s=self.edge(axis,end);diagonal[s]+=2*mask[s]
        diagonal/=self.h**2;diagonal[~self.fluid]=1
        if (diagonal[self.fluid]<=0).any(): raise ValueError('Isolated fluid cell')
        z=r/diagonal;direction=z.clone();rz=torch.sum(r.double()*z)
        relative=1.
        for it in range(max_iterations):
            checkpoint()
            ap=-self.divergence(self.gradient(direction))
            denom=torch.sum(direction.double()*ap)
            if denom<=0: raise ValueError('Projection lost positive definiteness')
            alpha=(rz/denom).float();p+=alpha*direction;r-=alpha*ap
            relative=float(torch.linalg.vector_norm(r))/initial
            if relative<tolerance: break
            z=r/diagonal;new_rz=torch.sum(r.double()*z);direction=z+(new_rz/rz).float()*direction;rz=new_rz
            if it%100==0:progress(iteration=it,relative_residual=relative)
        # Report the true residual, not only CG's recurrence estimate.
        grad=self.gradient(p); projected=[f-g for f,g in zip(self.faces,grad)]
        true_relative=float(torch.linalg.vector_norm(self.divergence(projected)))/initial
        if true_relative>tolerance*5: raise ValueError(f'Projection did not converge: {true_relative}')
        delta=sum(float((g.double()**2).sum()) for g in grad)
        norm=sum(float((f.double()**2).sum()) for f in self.faces)
        self.faces=projected;self._set_dt()
        return {'iterations':it+1,'relative_residual':true_relative,'velocity_correction_l2_fraction':math.sqrt(delta/max(norm,1e-30)), 'max_divergence_s_inv':float(self.divergence(projected).abs().max())}

    def _set_dt(self):
        loss=torch.zeros_like(self.c)
        for axis,(f,m) in enumerate(zip(self.faces,self.masks)):
            a,b,_=self.pair(axis)
            loss+=(torch.clamp(f[b],min=0)+torch.clamp(-f[a],min=0))/self.h
            loss+=(m[a].float()+m[b].float())*self.k/self.h**2
            # Open boundary zero value sits half a cell from the cell centre.
            for end in (0,-1):
                s=self.edge(axis,end);loss[s]+=m[s]*self.k/self.h**2
        peak=float(loss.max());self.max_dt=.8/peak if peak else float('inf')

    def step(self, dt, source_indices=(), source_mass_ug=()):
        if not math.isfinite(dt) or dt<=0 or dt>self.max_dt*(1+1e-6):raise ValueError('Unstable timestep')
        if len(source_indices):
            idx=torch.tensor(source_indices,dtype=torch.long,device=self.c.device)
            mass=torch.tensor(source_mass_ug,dtype=torch.float32,device=self.c.device)
            if idx.ndim!=1 or mass.shape!=idx.shape or not torch.isfinite(mass).all() or (mass<0).any() or (idx<0).any() or (idx>=self.c.numel()).any() or not self.fluid.flatten()[idx].all():raise ValueError('Invalid source cells/masses')
        delta=torch.zeros_like(self.c); escaped=torch.zeros((),dtype=torch.float64,device=self.c.device)
        for axis,(u,mask) in enumerate(zip(self.faces,self.masks)):
            a,b,m=self.pair(axis);f=torch.zeros_like(u)
            f[m]=(u[m]*torch.where(u[m]>=0,self.c[a],self.c[b])-self.k*(self.c[b]-self.c[a])/self.h)*mask[m]
            for end in (0,-1):
                s=self.edge(axis,end);outward=-1 if end==0 else 1
                f[s]=(u[s]*self.c[s]*(u[s]*outward>0)+outward*2*self.k*self.c[s]/self.h)*mask[s]
                escaped+=outward*f[s].double().sum()*self.h**2*dt
            delta-=(f[b]-f[a])*(dt/self.h)
        self.c+=delta
        if len(source_indices):
            self.c.flatten().index_add_(0,idx,mass/self.h**3)
            self.emitted_ug+=float(mass.double().sum())
        self.outflow_ug+=float(escaped);self.steps+=1

    def diagnostics(self):
        mass=float(self.c.double().sum())*self.h**3
        error=abs(mass+self.outflow_ug-self.emitted_ug)/max(self.emitted_ug,1.)
        if not torch.isfinite(self.c).all() or float(self.c.min()) < -1e-7 or error>2e-5:
            raise ValueError(f'Invalid concentration / mass closure: {error}')
        return {'stored_ug':mass,'emitted_ug':self.emitted_ug,'boundary_outflow_ug':self.outflow_ug,'relative_mass_error':error,'minimum_ug_m3':float(self.c.min()),'maximum_ug_m3':float(self.c.max()),'substeps':self.steps,'stable_dt_s':self.max_dt}
