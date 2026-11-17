"""Low-altitude wind-aware demo: A* on an 8 m terrain-following flight surface.
Not WavePDE; no flight dynamics or all-pairs/global continuous optimum claim.
"""
from pathlib import Path
import argparse,json,time,hashlib,heapq,math
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.sparse.csgraph import minimum_spanning_tree
from numba import njit

@njit(cache=True)
def astar(free,z,top,gmin,wind,source,target,max_wind):
    ny,nx=free.shape; n=ny*nx
    dist=np.full(n,np.inf); parent=np.full(n,-1,np.int32); closed=np.zeros(n,np.uint8)
    sy,sx=source; ty,tx=target; start=sy*nx+sx; goal=ty*nx+tx
    dist[start]=0.; heap=[(0.,start)]; count=0
    while heap:
        _,idx=heapq.heappop(heap)
        if closed[idx]:continue
        closed[idx]=1; count+=1
        if idx==goal:
            path=[idx]
            while path[-1]!=start:path.append(parent[path[-1]])
            return path[::-1],dist[idx],count
        if count>600000:break
        y,x=idx//nx,idx%nx
        for dy in range(-1,2):
            for dx in range(-1,2):
                if dx==0 and dy==0:continue
                yy,xx=y+dy,x+dx
                if yy<1 or yy>=ny-1 or xx<1 or xx>=nx-1:continue
                nxt=yy*nx+xx
                if closed[nxt] or not free[yy,xx] or not free[y,xx] or not free[yy,x]:continue
                za,zb=z[y,x],z[yy,xx]
                # Entire segment stays clear of all four touched columns; no corner cutting.
                roof=max(top[y,x],top[yy,xx],top[y,xx],top[yy,x])
                floor=min(gmin[y,x],gmin[yy,xx],gmin[y,xx],gmin[yy,x])
                if min(za,zb)<roof+3 or max(za,zb)>floor+38:continue
                vx,vy,vz=dx*8.,dy*8.,zb-za
                length=math.sqrt(vx*vx+vy*vy+vz*vz)
                ex,ey,ez=vx/length,vy/length,vz/length
                wx=(wind[0,y,x]+wind[0,yy,xx])*.5; wy=(wind[1,y,x]+wind[1,yy,xx])*.5; wz=(wind[2,y,x]+wind[2,yy,xx])*.5
                aa=(ex*ex+ey*ey)/144+ez*ez/9
                bb=(ex*wx+ey*wy)/144+ez*wz/9
                cc=(wx*wx+wy*wy)/144+wz*wz/9-1
                disc=bb*bb-aa*cc
                if disc<=0:continue
                speed=(bb+math.sqrt(disc))/aa
                if speed<=.1:continue
                cost=dist[idx]+length/speed
                if cost<dist[nxt]:
                    dist[nxt]=cost;parent[nxt]=idx
                    h=math.sqrt(((xx-tx)*8.)**2+((yy-ty)*8.)**2+(zb-z[ty,tx])**2)/(12+max_wind)
                    heapq.heappush(heap,(cost+h,nxt))
    return [-1],np.inf,count

def sample_wind(volume,xyz,ground):
    # Source wind uses flat/terrain-normalized z; explicit transfer by AGL.
    xy=(xyz[:,:2]+4096)/2-.5
    terrain=map_coordinates(ground,[xy[:,1],xy[:,0]],order=1,mode='nearest')
    zz=(xyz[:,2]-terrain+2)/8-.5
    xx=(xyz[:,0]+4098)/8-.5; yy=(xyz[:,1]+4098)/8-.5
    return np.stack([map_coordinates(volume[k],[zz,yy,xx],order=1,mode='nearest') for k in range(3)],axis=1)

def segment_times(points,wind):
    d=np.diff(points,axis=0);length=np.linalg.norm(d,axis=1);e=d/length[:,None]
    inv=np.array([1/144,1/144,1/9]); aa=np.sum(e*e*inv,axis=1);bb=np.sum(e*wind*inv,axis=1);cc=np.sum(wind*wind*inv,axis=1)-1
    discriminant=bb*bb-aa*cc
    if np.any(discriminant<=0):raise ValueError('Wind exceeds feasible airspeed ellipsoid')
    speed=(bb+np.sqrt(discriminant))/aa
    if np.any(speed<=0):raise ValueError('Non-positive ground speed')
    return length/speed

def dense(points,step=.5):
    chunks=[]
    for a,b in zip(points[:-1],points[1:]):
        count=max(1,math.ceil(float(np.linalg.norm(b-a))/step))
        chunks.append(a+(b-a)*np.arange(count)[:,None]/count)
    return np.concatenate(chunks+[points[-1:]])

def audit(points,ground,top):
    p=dense(points);xy=np.floor((p[:,:2]+4096)/2).astype(int);x,y=xy[:,0],xy[:,1]
    g=ground[y,x];obstacle=top[y,x];agl=p[:,2]-g
    collision=(obstacle>g+.5)&(p[:,2]<obstacle+3-1e-4)
    return {'passed':bool(not collision.any() and agl.min()>=-.02 and agl.max()<=40),
      'samples':len(p),'max_agl_m':float(agl.max()),'min_agl_m':float(agl.min()),'obstacle_violations':int(collision.sum()),
      'sampling_m':.5,'collision_model':'2 m column raster; cruise also uses conservative 4 m horizontal padding + 3 m vertical margin on 8 m routing cells'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--wind',required=True);ap.add_argument('--output',required=True);ap.add_argument('--limit',type=int);args=ap.parse_args()
    root=Path(args.input);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    data=np.load(root/'planner_inputs.npz');ground=data['ground'];top=data['top'];z=data['altitude'];free=data['free']
    stations=json.loads((root/'stations.json').read_text());volume=np.load(args.wind,mmap_mode='r')
    yy,xx=np.indices(z.shape); xyz=np.stack([-4096+(xx.ravel()+.5)*8,-4096+(yy.ravel()+.5)*8,z.ravel()],axis=1)
    flow=sample_wind(volume,xyz,ground).T.reshape(3,*z.shape).astype(np.float32); maxwind=float(np.linalg.norm(flow,axis=0).max())
    xy=np.array([s['position_enu_m'][:2] for s in stations]); dd=np.linalg.norm(xy[:,None]-xy[None,:],axis=2)
    edges=set()
    for i in range(len(stations)):
        for j in np.argsort(dd[i])[1:4]:edges.add(tuple(sorted((i,int(j)))))
    mst=minimum_spanning_tree(dd).tocoo()
    for i,j in zip(mst.row,mst.col):edges.add(tuple(sorted((int(i),int(j)))))
    pairs=sorted((i,j) for a,b in edges for i,j in [(a,b),(b,a)])
    if args.limit:pairs=pairs[:args.limit]
    routes=[];failures=[];beg=time.time()
    for number,(i,j) in enumerate(pairs):
        a,b=stations[i],stations[j];start=(a['row'],a['col']);end=(b['row'],b['col'])
        route,cost,expansions=astar(free,z,data['blocked_top'],data['gmin'],flow,start,end,maxwind)
        if route[0]<0:failures.append({'from':a['id'],'to':b['id'],'reason':'No surface route found within expansion limit','expansions':expansions})
        else:
            idx=np.array(route); y,x=idx//1024,idx%1024
            cruise=np.stack([-4096+(x+.5)*8,-4096+(y+.5)*8,z[y,x]],axis=1)
            p=np.vstack([a['position_enu_m'],np.array(a['position_enu_m'])+[0,0,12],cruise,np.array(b['position_enu_m'])+[0,0,12],b['position_enu_m']])
            check=audit(p,ground,top)
            if not check['passed']:failures.append({'from':a['id'],'to':b['id'],'reason':'Fine raster validation failed','audit':check})
            else:
                mids=(p[:-1]+p[1:])*.5;w=sample_wind(volume,mids,ground); dt=segment_times(p,w); times=np.r_[0,np.cumsum(dt)]
                calm=segment_times(p,np.zeros_like(w)).sum()
                straight=audit(np.stack([cruise[0],cruise[-1]]),ground,top)
                routes.append({'id':a['id']+'-'+b['id'],'from':a['id'],'to':b['id'],'points_enu_m':p.round(4).tolist(),'times_s':times.round(5).tolist(),'wind_enu_mps':sample_wind(volume,p,ground).round(4).tolist(),'duration_s':float(times[-1]),'calm_same_path_s':float(calm),'distance_m':float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()),'straight_distance_m':float(np.linalg.norm(cruise[-1]-cruise[0])),'straight_blocked':not straight['passed'],'audit':check})
        status={'attempted':number+1,'total':len(pairs),'passed':len(routes),'failed':len(failures),'elapsed_s':round(time.time()-beg,1)}
        (out/'progress.json').write_text(json.dumps(status));print(json.dumps(status),flush=True)
    connected=set(s for r in routes for s in (r['from'],r['to']))
    provenance=json.loads((root/'input-provenance.json').read_text())
    manifest={'schema_version':'canopy-wind-astar-demo-1','scene_id':'imperial_corridor_8km','algorithm':'Wind-weighted A* on an 8 m terrain-following cruise surface with checked vertical takeoff/landing legs','air_speed_xy_mps':12,'air_speed_z_mps':3,'ceiling_agl_m':40,'nominal_cruise_agl_m':24,'stations':stations,'routes':routes,'failures':failures,'summary':{**status,'connected_stations':len(connected),'blocked_straight_routes':sum(r['straight_blocked'] for r in routes),'maximum_agl_m':max((r['audit']['max_agl_m'] for r in routes),default=0)},'wind':{'source':str(args.wind),'sha256':hashlib.sha256(Path(args.wind).read_bytes()).hexdigest(),'frame':'ENU','frozen_model_time_s':7500,'origin_enu_m':[-4098,-4098,-2],'cell_m':8,'terrain_adapter':'Sample original flat-geometry field at local AGL. Wind not recomputed on terrain-restored geometry. No CFD reference validation.'},'provenance':provenance,'limitations':['Synthetic station locations, not real landing sites.','Static 3D model wind at 7500 s; no gust/forecast or rotor dynamics.','Routes are optimal only on the constrained 8 m cruise surface with endpoint-averaged wind costs; not arbitrary 3D trajectories.','Collision evidence covers the rasterized 2.5D geometry, not exact mesh, wires or moving objects.','Time is kinematic segment integration, not measured flight performance.','Only selected neighbouring station pairs are precomputed; not all 9900 ordered pairs.']}
    (out/'routes.json').write_text(json.dumps(manifest,separators=(',',':')))
if __name__=='__main__':main()
