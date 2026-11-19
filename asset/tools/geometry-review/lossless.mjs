// Re-encode storage only. Never quantize, filter, reorder, weld or simplify.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {MeshoptEncoder, MeshoptDecoder} from 'meshoptimizer';

export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const align4 = n => Math.ceil(n / 4) * 4;
const sizes = {5120:1,5121:1,5122:2,5123:2,5125:4,5126:4};
const components = {SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT2:4,MAT3:9,MAT4:16};

export function readGlb(bytes) {
  const b = Buffer.from(bytes);
  assert.equal(b.readUInt32LE(0), 0x46546c67, 'Expected GLB');
  assert.equal(b.readUInt32LE(4), 2, 'Expected glTF 2');
  assert.equal(b.readUInt32LE(8), b.length, 'GLB length mismatch');
  assert.equal(b.readUInt32LE(16), 0x4e4f534a, 'Expected JSON chunk');
  const end = 20 + b.readUInt32LE(12), json = JSON.parse(b.subarray(20, end));
  assert.equal(b.readUInt32LE(end + 4), 0x004e4942, 'Expected binary chunk');
  assert.equal(end + 8 + b.readUInt32LE(end), b.length, 'Unexpected GLB chunks');
  return {json, bin:b.subarray(end + 8)};
}

export function writeGlb(json, bytes) {
  const j = Buffer.from(JSON.stringify(json)), b = Buffer.from(bytes);
  const out = Buffer.alloc(12 + 8 + align4(j.length) + 8 + align4(b.length));
  out.writeUInt32LE(0x46546c67, 0); out.writeUInt32LE(2, 4); out.writeUInt32LE(out.length, 8);
  out.writeUInt32LE(align4(j.length), 12); out.writeUInt32LE(0x4e4f534a, 16);
  out.fill(32, 20, 20 + align4(j.length)); j.copy(out, 20);
  const offset = 20 + align4(j.length);
  out.writeUInt32LE(align4(b.length), offset); out.writeUInt32LE(0x004e4942, offset + 4);
  b.copy(out, offset + 8); return out;
}

export async function compressGlb(source) {
  await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready]);
  const {json:original, bin} = readGlb(source), json = structuredClone(original);
  assert.equal(json.buffers.length, 1, 'Only one embedded source buffer is supported');
  assert(!json.buffers[0].uri, 'External source buffers are not accepted');
  assert(!(json.extensionsUsed || []).some(x=>/meshopt|draco/.test(x)), 'Already compressed source');
  const parts = [], proofs = []; let offset = 0, fallbackLength = 0, compressedViews = 0;
  function append(bytes) {
    const start = offset; parts.push(Buffer.from(bytes)); offset += bytes.length;
    const pad = align4(offset) - offset; if(pad) parts.push(Buffer.alloc(pad)); offset += pad;
    return start;
  }
  json.bufferViews = original.bufferViews.map((view, id) => {
    assert.equal(view.buffer, 0); assert(!view.extensions, 'Unsupported source buffer-view extension');
    const start = view.byteOffset || 0, raw = bin.subarray(start, start + view.byteLength);
    assert.equal(raw.length, view.byteLength, 'Buffer view out of range');
    const accessors = original.accessors.filter(a => a.bufferView === id);
    const accessor = accessors[0];
    let stride = view.byteStride || (accessor && sizes[accessor.componentType] * components[accessor.type]);
    const mode = view.target === 34963 ? 'INDICES' : 'ATTRIBUTES';
    const compatible = accessor && !accessors.some(a=>a.sparse) && raw.length > 0 &&
      raw.length % stride === 0 && (mode === 'INDICES' ? [2,4].includes(stride) : stride%4 === 0 && stride<=256);
    let encoded, decoded;
    if (compatible) {
      // INDICES preserves the exact index sequence, including triangle winding.
      encoded = MeshoptEncoder.encodeGltfBuffer(raw, raw.length / stride, stride, mode);
      decoded = new Uint8Array(raw.length);
      MeshoptDecoder.decodeGltfBuffer(decoded, raw.length / stride, stride, encoded, mode, 'NONE');
      assert.deepEqual(Buffer.from(decoded), raw, `Lossless round-trip failed for view ${id}`);
    }
    const use = encoded && encoded.length < raw.length;
    proofs.push({view:id, bytes:raw.length, sha256:sha256(raw), decoded_sha256:sha256(use ? decoded : raw), compressed:!!use});
    if (!use) return {...view, buffer:0, byteOffset:append(raw)};
    const result = {...view, buffer:1, byteOffset:fallbackLength,
      extensions:{EXT_meshopt_compression:{buffer:0,byteOffset:append(encoded),byteLength:encoded.length,
        byteStride:stride,count:raw.length / stride,mode,filter:'NONE'}}};
    fallbackLength += align4(raw.length); compressedViews++; return result;
  });
  if (compressedViews) {
    json.extensionsUsed = [...new Set([...(json.extensionsUsed||[]), 'EXT_meshopt_compression'])];
    json.extensionsRequired = [...new Set([...(json.extensionsRequired||[]), 'EXT_meshopt_compression'])];
  }
  const binary = Buffer.concat(parts);
  json.buffers = [{...original.buffers[0],byteLength:binary.length}];
  if(compressedViews) json.buffers.push({byteLength:fallbackLength,extensions:{EXT_meshopt_compression:{fallback:true}}});
  // Preserve every scene, node, accessor, primitive, material, image and animation descriptor.
  for(const key of Object.keys(original)) if(!['buffers','bufferViews','extensionsUsed','extensionsRequired'].includes(key))
    assert.deepEqual(json[key], original[key], `Semantic descriptor changed: ${key}`);
  const output=writeGlb(json,binary);
  // Verify the serialized GLB, including offsets, rather than only codec inputs.
  const packed=readGlb(output);
  for(let id=0;id<packed.json.bufferViews.length;id++) {
    const view=packed.json.bufferViews[id],ext=view.extensions?.EXT_meshopt_compression;
    let decoded;
    if(ext) {
      decoded=new Uint8Array(view.byteLength);
      MeshoptDecoder.decodeGltfBuffer(decoded,ext.count,ext.byteStride,
        packed.bin.subarray(ext.byteOffset,ext.byteOffset+ext.byteLength),ext.mode,ext.filter);
    } else decoded=packed.bin.subarray(view.byteOffset,view.byteOffset+view.byteLength);
    assert.equal(sha256(decoded),proofs[id].sha256,`Serialized GLB view ${id} differs`);
  }
  return {bytes:output, proofs, compressedViews,
    triangles:(json.meshes||[]).reduce((sum,m)=>sum+m.primitives.reduce((n,p)=>n+((p.mode??4)===4 ? json.accessors[p.indices??p.attributes.POSITION].count/3 : 0),0),0)};
}
