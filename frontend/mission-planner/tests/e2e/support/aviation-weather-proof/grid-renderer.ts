import * as THREE from 'three';
import type { Descriptor } from './model';
import { barb } from './sampling';
export const samplingShader = `
 uniform sampler2D packedGrid; uniform vec2 size; uniform float scale; uniform float offset; uniform int diagnostic;
 varying vec3 earth;
 vec3 node(vec2 p){vec4 c=texture2D(packedGrid,(p+0.5)/size);float q=floor(c.r*255.0+0.5)+256.0*floor(c.g*255.0+0.5);return vec3(q>=32768.0?q-65536.0:q,floor(c.b*255.0+0.5),0.0);}
 vec2 geography(){vec3 p=normalize(earth);return vec2(degrees(atan(-p.z,p.x)),degrees(asin(clamp(p.y,-1.0,1.0))));}
 vec2 sampleValue(){vec2 geo=geography();float lon=geo.x;float lat=geo.y;vec2 q=vec2(mod(lon+180.0,360.0)*2.0,(90.0-lat)*2.0);
 if(q.y<0.0||q.y>size.y-1.0||(size.x<720.0&&q.x>size.x-1.0))return vec2(0.0,1.0);
 vec2 lo=floor(q),hi=min(lo+1.0,size-1.0);if(size.x==720.0)hi.x=mod(lo.x+1.0,size.x);
 vec3 a=node(lo),b=node(vec2(hi.x,lo.y)),c=node(vec2(lo.x,hi.y)),d=node(hi);float mask=max(max(a.y,b.y),max(c.y,d.y));
 return vec2(mix(mix(a.x,b.x,fract(q.x)),mix(c.x,d.x,fract(q.x)),fract(q.y)),mask);}
 void main(){if(diagnostic>=2){vec2 geo=geography();float value=diagnostic==2?(geo.x+180.0)/360.0:diagnostic==3?(geo.y+90.0)/180.0:diagnostic==4?(earth.x+3.0)/6.0:diagnostic==5?(earth.y+3.0)/6.0:(earth.z+3.0)/6.0;float q=floor(value*16777215.0+0.5);gl_FragColor=vec4(floor(q/65536.0),mod(floor(q/256.0),256.0),mod(q,256.0),255.0)/255.0;return;}vec2 s=sampleValue();if(diagnostic==1){float q=floor(s.x+32768.0+0.5);gl_FragColor=vec4(floor(q/256.0)/255.0,mod(q,256.0)/255.0,s.y/255.0,1.0);return;}
 if(s.y>0.0)discard;float t=clamp((s.x*scale+offset-190.0)/120.0,0.0,1.0);gl_FragColor=vec4(t,0.25,1.0-t,0.4);}
`;
export function earthPoint(lat: number, lon: number, r = 2.012) {
  const a = (lat * Math.PI) / 180,
    b = (lon * Math.PI) / 180;
  return new THREE.Vector3(
    r * Math.cos(a) * Math.cos(b),
    r * Math.sin(a),
    -r * Math.cos(a) * Math.sin(b)
  );
}
export function gridMesh(d: Descriptor, values: Int16Array, mask: Uint8Array) {
  const packed = new Uint8Array(values.length * 4);
  for (let i = 0; i < values.length; i++) {
    packed[i * 4] = values[i] & 255;
    packed[i * 4 + 1] = (values[i] >> 8) & 255;
    packed[i * 4 + 2] = mask[i];
    packed[i * 4 + 3] = 255;
  }
  const texture = new THREE.DataTexture(
    packed,
    d.grid.width,
    d.grid.height,
    THREE.RGBAFormat
  );
  texture.minFilter = texture.magFilter = THREE.NearestFilter;
  texture.generateMipmaps = false;
  texture.needsUpdate = true;
  const geometry = new THREE.SphereGeometry(2.012, 180, 90);
  const material = new THREE.ShaderMaterial({
    uniforms: {
      packedGrid: { value: texture },
      size: { value: new THREE.Vector2(d.grid.width, d.grid.height) },
      scale: { value: d.components.t.scale },
      offset: { value: d.components.t.offset },
      diagnostic: { value: 0 },
    },
    vertexShader:
      'varying vec3 earth;void main(){earth=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
    fragmentShader: samplingShader,
    transparent: true,
    depthWrite: false,
    toneMapped: false,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = 'Aviation diagnostic scalar';
  mesh.renderOrder = 20;
  return {
    mesh,
    bytes: geometryBytes(geometry) + packed.byteLength,
    decoded: geometryBytes(geometry) + packed.byteLength,
    dispose: () => {
      texture.dispose();
      geometry.dispose();
      material.dispose();
    },
  };
}
export function geometryBytes(g: THREE.BufferGeometry) {
  return (
    Object.values(g.attributes).reduce((n, a) => n + a.array.byteLength, 0) +
    (g.index?.array.byteLength ?? 0)
  );
}
export function windBarbs(
  d: Descriptor,
  u: Int16Array,
  v: Int16Array,
  mask: Uint8Array
) {
  const vertices: number[] = [];
  let count = 0;
  for (let y = 10; y < d.grid.height - 10; y += 12)
    for (let x = 0; x < d.grid.width; x += 12) {
      const i = y * d.grid.width + x;
      if (mask[i] || count >= 2000) continue;
      const glyph = barb(
        u[i] * d.components.u.scale! + d.components.u.offset!,
        v[i] * d.components.v.scale! + d.components.v.offset!
      );
      const lat = 90 - y * 0.5,
        lon = -180 + x * 0.5,
        base = earthPoint(lat, lon, 2.028),
        east = earthPoint(0, lon + 90, 1),
        north = earthPoint(lat + 90, lon, 1),
        shaft = east
          .clone()
          .multiplyScalar(glyph.fromEast)
          .addScaledVector(north, glyph.fromNorth),
        side = base.clone().normalize().cross(shaft).normalize();
      const end = base.clone().addScaledVector(shaft, 0.052);
      vertices.push(...base.toArray(), ...end.toArray());
      let remaining = glyph.knots,
        position = 0.052;
      while (remaining >= 5 && position > 0) {
        const amount = remaining >= 50 ? 50 : remaining >= 10 ? 10 : 5,
          p = base.clone().addScaledVector(shaft, position),
          tip = p
            .clone()
            .addScaledVector(side, amount === 5 ? 0.01 : 0.02)
            .addScaledVector(shaft, -0.009);
        vertices.push(...p.toArray(), ...tip.toArray());
        if (amount === 50)
          vertices.push(
            ...tip.toArray(),
            ...p.clone().addScaledVector(shaft, -0.009).toArray()
          );
        position -= amount === 50 ? 0.014 : 0.008;
        remaining -= amount;
      }
      count++;
    }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(vertices, 3)
  );
  const material = new THREE.LineBasicMaterial({
    color: 0xffffff,
    depthWrite: false,
  });
  const mesh = new THREE.LineSegments(geometry, material);
  mesh.name = 'Aviation diagnostic wind FROM barbs';
  mesh.renderOrder = 21;
  return {
    mesh,
    count,
    bytes: geometryBytes(geometry),
    dispose: () => {
      geometry.dispose();
      material.dispose();
    },
  };
}
