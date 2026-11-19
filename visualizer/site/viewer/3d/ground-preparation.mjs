import {buildSurfaceArrays} from './surface-geometry.mjs';

// One worker bounds simultaneous geometry construction. Transfer ownership of
// arrays instead of copying every vertex back onto the main thread.
export function createGroundPreparation(dem) {
  let worker = null, nextId = 0, failure = null;
  const pending = new Map();
  const {nx, ny, x0, y0, dx} = dem.data;
  const grid = {data:{nx,ny,x0,y0,dx},h:dem.h};
  if (typeof Worker !== 'undefined') {
    try {
      worker = new Worker(new URL('./ground-geometry-worker.mjs', import.meta.url), {type:'module'});
      worker.postMessage({type:'init',dem:grid});
    } catch (error) {
      worker?.terminate(); worker = null;
      console.warn('Background geometry preparation unavailable; using the same main-thread calculation.', error);
    }
  }
  if (worker) {
    worker.onmessage = ({data}) => {
      const item = pending.get(data.id);
      if (!item) return;
      pending.delete(data.id);
      data.error ? item.reject(new Error(data.error)) : item.resolve(data.result);
    };
    worker.onerror = event => {
      failure = new Error(event.message || 'Background geometry preparation failed');
      for (const item of pending.values()) item.reject(failure);
      pending.clear(); worker.terminate();
    };
  }
  return {
    mode:worker ? 'worker' : 'main-thread',
    build(original, elevated) {
      if (failure) return Promise.reject(failure);
      if (!worker) return Promise.resolve().then(() => buildSurfaceArrays(original, elevated, grid));
      return new Promise((resolve,reject) => {
        const id=nextId++; pending.set(id,{resolve,reject});
        try { worker.postMessage({id,original,elevated},[original,elevated]); }
        catch (error) { pending.delete(id); reject(error); }
      });
    },
    dispose() {
      failure = new Error('Ground preparation disposed');
      for (const item of pending.values()) item.reject(failure);
      pending.clear(); worker?.terminate();
    },
  };
}
