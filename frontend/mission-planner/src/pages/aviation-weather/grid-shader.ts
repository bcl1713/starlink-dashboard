// Reconstruct the fragment's geographic location on its actual triangle plane;
// interpolated vertex latitude/longitude is inaccurate at seams and poles.
export const gridVertexShader = `attribute vec4 trianglePlane; flat varying vec4 facePlane;
void main(){facePlane=trianglePlane;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`;
const samplingShader = `
uniform vec2 size; uniform int diagnostic; flat varying vec4 facePlane;
uniform mat4 inverseProjection; uniform mat4 cameraWorld; uniform vec3 eye; uniform vec2 framebuffer;
vec3 fragmentPoint(){vec2 ndc=gl_FragCoord.xy/framebuffer*2.0-1.0;vec4 view=inverseProjection*vec4(ndc,1.0,1.0);vec3 farPoint=(cameraWorld*vec4(view.xyz/view.w,1.0)).xyz;vec3 ray=farPoint-eye;return eye+ray*((facePlane.w-dot(facePlane.xyz,eye))/dot(facePlane.xyz,ray));}
vec2 node(sampler2D packedGrid,vec2 p){vec4 c=texture2D(packedGrid,(p+0.5)/size);float q=floor(c.r*255.0+0.5)+256.0*floor(c.g*255.0+0.5);return vec2(q>=32768.0?q-65536.0:q,floor(c.b*255.0+0.5));}
vec2 sampleValue(sampler2D packedGrid){vec3 p=fragmentPoint();float lon=degrees(atan(-p.z,p.x)),lat=degrees(atan(p.y,length(p.xz)));
vec2 q=vec2(mod(lon+180.0,360.0)*2.0,clamp((90.0-lat)*2.0,0.0,360.0));
vec2 lo=floor(q),hi=vec2(mod(lo.x+1.0,size.x),min(lo.y+1.0,size.y-1.0)),f=fract(q);
vec2 a=node(packedGrid,lo),b=node(packedGrid,vec2(hi.x,lo.y)),c=node(packedGrid,vec2(lo.x,hi.y)),d=node(packedGrid,hi);
vec4 w=vec4((1.0-f.x)*(1.0-f.y),f.x*(1.0-f.y),(1.0-f.x)*f.y,f.x*f.y);
float mask=0.0;if(w.x>0.0)mask=max(mask,a.y);if(w.y>0.0)mask=max(mask,b.y);if(w.z>0.0)mask=max(mask,c.y);if(w.w>0.0)mask=max(mask,d.y);
return vec2(dot(vec4(a.x,b.x,c.x,d.x),w),mask);}

vec4 signedReadback(vec2 s){float q=floor(s.x+32768.0+0.5);return vec4(floor(q/256.0)/255.0,mod(q,256.0)/255.0,s.y/255.0,1.0);}
`;
export const gridFragmentShader = `
uniform sampler2D packedGrid; uniform float scale; uniform float offset;
${samplingShader}
void main(){vec2 s=sampleValue(packedGrid);if(diagnostic==1||diagnostic==3){gl_FragColor=signedReadback(s);return;}
if(s.y>0.0)discard;float t=clamp((s.x*scale+offset-273.15+80.0)/120.0,0.0,1.0);
vec3 cold=vec3(0.24,0.15,0.72),middle=vec3(0.20,0.75,0.87),hot=vec3(0.94,0.25,0.14);
vec3 color=t<0.5?mix(cold,middle,t*2.0):mix(middle,hot,(t-0.5)*2.0);gl_FragColor=vec4(color,0.45);}`;
export const windFragmentShader = `
uniform sampler2D packedU; uniform sampler2D packedV; uniform vec2 windScale; uniform vec2 windOffset;
uniform float windStops[7]; uniform vec3 windColors[7];
${samplingShader}
vec3 windPalette(float knots){
  if(knots<=windStops[0])return windColors[0];
  for(int i=0;i<6;i++)if(knots<=windStops[i+1])return mix(windColors[i],windColors[i+1],(knots-windStops[i])/(windStops[i+1]-windStops[i]));
  return windColors[6];
}
void main(){
  vec2 u=sampleValue(packedU),v=sampleValue(packedV);float mask=max(u.y,v.y);
  if(diagnostic==1){gl_FragColor=signedReadback(u);return;}
  if(diagnostic==2){gl_FragColor=signedReadback(v);return;}
  float knots=length(vec2(u.x,v.x)*windScale+windOffset)*1.9438444924406;
  if(diagnostic==4){float q=floor(knots*100.0+0.5);gl_FragColor=vec4(floor(q/65536.0)/255.0,mod(floor(q/256.0),256.0)/255.0,mod(q,256.0)/255.0,mask/255.0);return;}
  if(mask>0.0)discard;
  gl_FragColor=vec4(windPalette(knots),diagnostic==5?1.0:0.45);
}`;
