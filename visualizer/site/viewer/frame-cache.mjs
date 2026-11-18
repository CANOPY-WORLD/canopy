// A byte-bounded cache for read-only frames. Superseded loads may finish for their
// caller, but cannot repopulate the cache after a widget changes its source files.
export class FrameCache {
  constructor(maxBytes) {
    this.maxBytes = maxBytes;
    this.values = new Map();
    this.pending = new Map();
    this.bytes = 0;
    this.sources = null;
    this.generation = 0;
  }
  retainSources(sources) {
    const next = new Set(sources);
    if (this.sources && next.size === this.sources.size && [...next].every(s => this.sources.has(s))) return;
    this.sources = next;
    this.generation++;
    for (const [key, entry] of this.values) if (!next.has(entry.source)) {
      this.bytes -= entry.value.byteLength;
      this.values.delete(key);
    }
  }
  async get(source, index, load) {
    const key = `${source}#${index}`;
    if (this.values.has(key)) {
      const entry = this.values.get(key);
      this.values.delete(key);
      this.values.set(key, entry);
      return entry.value;
    }
    const generation = this.generation;
    const pendingKey = `${generation}:${key}`;
    if (this.pending.has(pendingKey)) return this.pending.get(pendingKey);
    const promise = Promise.resolve().then(load).then(value => {
      if (generation === this.generation && (!this.sources || this.sources.has(source)) && value.byteLength <= this.maxBytes) {
        while (this.bytes + value.byteLength > this.maxBytes && this.values.size) {
          const first = this.values.keys().next().value;
          this.bytes -= this.values.get(first).value.byteLength;
          this.values.delete(first);
        }
        this.values.set(key, {source, value});
        this.bytes += value.byteLength;
      }
      return value;
    }).finally(() => this.pending.delete(pendingKey));
    this.pending.set(pendingKey, promise);
    return promise;
  }
  info() { return {bytes: this.bytes, frames: this.values.size, pending: this.pending.size, cap: this.maxBytes}; }
}
