// Bounded download + preparation slots. A completed download keeps its slot
// until preparation finishes, so decoded backlogs cannot grow without bound.
export function createAssetQueue({concurrency = 4, retries = 2, load, prepare,
  commit, discard = () => {}, onChange = () => {}, retryDelay = n => 500 * n,
  yieldFrame = () => new Promise(resolve => setTimeout(resolve, 0))}) {
  const jobs = new Map();
  let active = 0, stopped = false, preparation = Promise.resolve(), timer = null;
  const stats = {requests: 0, retries: 0, cancelled: 0, completed: 0, bytes: 0, peakActive: 0};
  const live = job => !stopped && jobs.get(job.key) === job && !job.controller.signal.aborted;
  function pump() {
    clearTimeout(timer); timer = null;
    if (stopped) return;
    const queued = [...jobs.values()].filter(j => j.state === 'queued');
    const now = Date.now();
    queued.sort((a, b) => a.priority - b.priority);
    for (const job of queued) {
      if (active >= concurrency) break;
      if (job.after <= now) run(job);
    }
    const waits = queued.filter(j => j.state === 'queued' && j.after > now);
    if (waits.length) timer = setTimeout(pump, Math.max(1, Math.min(...waits.map(j => j.after)) - now));
  }
  async function run(job) {
    active++; stats.peakActive = Math.max(stats.peakActive, active);
    job.state = 'downloading'; job.received = 0; stats.requests++; onChange();
    let result;
    try {
      let bytes = await load(job.item, job.controller.signal, count => {
        if (live(job)) { job.received = count; onChange(); }
      });
      stats.bytes += bytes.byteLength;
      if (!live(job)) return;
      job.state = 'preparing'; onChange();
      // Serialize parse/attach work and give input/painting a turn between files.
      const task = preparation.then(async () => {
        await yieldFrame();
        if (!live(job)) return;
        result = await prepare(bytes, job.item);
        bytes = null;
        if (!live(job)) { discard(result); result = undefined; return; }
        commit(result, job.item); result = undefined;
        stats.completed++; jobs.delete(job.key);
      });
      preparation = task.catch(() => {});
      await task;
    } catch (error) {
      if (result !== undefined) discard(result);
      if (!live(job)) return;
      job.error = error;
      if (job.attempt++ < retries) {
        stats.retries++; job.state = 'queued'; job.after = Date.now() + retryDelay(job.attempt);
      } else job.state = 'failed';
    } finally { active--; onChange(); pump(); }
  }
  return {
    stats,
    add(key, item, priority = 0) {
      if (stopped) return;
      const current = jobs.get(key);
      if (current) { current.priority = priority; return; }
      jobs.set(key, {key, item, priority, state: 'queued', received: 0, attempt: 0, after: 0, controller: new AbortController()});
      // Enqueue a batch before choosing its first highest-priority jobs.
      queueMicrotask(pump);
    },
    cancel(key) {
      const job = jobs.get(key); if (!job) return;
      jobs.delete(key); job.controller.abort(); stats.cancelled++; onChange(); pump();
    },
    retry() {
      for (const job of jobs.values()) if (job.state === 'failed') {
        job.state = 'queued'; job.attempt = 0; job.after = 0;
      }
      pump();
    },
    snapshot() { return [...jobs.values()].map(({key, item, priority, state, received, error}) =>
      ({key, bytes: item.bytes ?? 0, priority, state, received, error: error?.message})); },
    dispose() {
      stopped = true; clearTimeout(timer);
      for (const job of jobs.values()) job.controller.abort();
      jobs.clear();
    },
  };
}

export async function fetchAsset(item, signal, onProgress = () => {}) {
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  signal.addEventListener('abort', abort, {once: true});
  if (signal.aborted) abort();
  let timer;
  const reset = () => { clearTimeout(timer); timer = setTimeout(() => controller.abort(new Error('Asset transfer stalled')), 30000); };
  reset();
  try {
    const response = await fetch(item.url, {signal: controller.signal});
    if (!response.ok) throw new Error(`Asset HTTP ${response.status}: ${item.url}`);
    // The inventory size is the unencoded GLB length, also on an HTTP-gzip host.
    const expected = Number.isSafeInteger(item.bytes) && item.bytes > 0 ? item.bytes : null;
    const reader = response.body?.getReader();
    if (!reader) {
      const buffer = await response.arrayBuffer();
      if (expected !== null && buffer.byteLength !== expected) throw new Error('Asset size differs from tile index');
      onProgress(buffer.byteLength); return buffer;
    }
    const target = expected === null ? null : new Uint8Array(expected), chunks = [];
    let count = 0;
    try {
      for (;;) {
        const {done, value} = await reader.read(); if (done) break;
        reset();
        if (target && count + value.byteLength > expected) throw new Error('Asset exceeds tile index size');
        if (target) target.set(value, count); else chunks.push(value);
        count += value.byteLength; onProgress(count);
      }
    } finally { reader.releaseLock(); }
    if (target) {
      if (count !== expected) throw new Error('Asset is shorter than tile index size');
      return target.buffer;
    }
    const buffer = new Uint8Array(count); let offset = 0;
    for (const chunk of chunks) { buffer.set(chunk, offset); offset += chunk.byteLength; }
    return buffer.buffer;
  } finally { clearTimeout(timer); controller.abort(); signal.removeEventListener('abort', abort); }
}
