import {buildSurfaceArrays} from './surface-geometry.mjs';

let dem;
self.onmessage = ({data}) => {
  if (data.type === 'init') { dem = data.dem; return; }
  const {id, original, elevated} = data;
  try {
    const result = buildSurfaceArrays(original, elevated, dem);
    const buffers = Object.values(result).flatMap(attributes => Object.values(attributes).map(array => array.buffer));
    self.postMessage({id, result}, buffers);
  } catch (error) {
    self.postMessage({id, error: error.message});
  }
};
