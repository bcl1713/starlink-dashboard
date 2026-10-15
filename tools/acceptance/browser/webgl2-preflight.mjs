/** Bounded WebGL2 capability projection safe for sealed platform evidence. */
export function webgl2Preflight() {
  const maximumFieldBytes = 512;
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl2');
  if (!gl) throw new Error('platform WebGL2 preflight failed');
  const debug = gl.getExtension('WEBGL_debug_renderer_info');
  const result = {
    renderer: debug
      ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)
      : gl.getParameter(gl.RENDERER),
    vendor: debug
      ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL)
      : gl.getParameter(gl.VENDOR),
    version: gl.getParameter(gl.VERSION),
  };
  if (
    !Object.values(result).every(
      (value) =>
        typeof value === 'string'
        && value.trim()
        && new TextEncoder().encode(value).byteLength <= maximumFieldBytes,
    )
  ) {
    throw new Error('platform WebGL2 preflight failed');
  }
  return result;
}
