// Reconstruct the fragment's geographic location on its actual triangle plane;
// interpolated vertex latitude/longitude is inaccurate at seams and poles.
export const gridVertexShader = `attribute vec4 trianglePlane; flat varying vec4 facePlane;
void main(){facePlane=trianglePlane;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`;
export const gridFragmentShader = `
uniform sampler2D packedGrid; uniform vec2 size; uniform float scale; uniform float offset;
uniform int diagnostic; flat varying vec4 facePlane;
uniform mat4 inverseProjection; uniform mat4 cameraWorld; uniform vec3 eye; uniform vec2 framebuffer;
vec3 fragmentPoint(){vec2 ndc=gl_FragCoord.xy/framebuffer*2.0-1.0;vec4 view=inverseProjection*vec4(ndc,1.0,1.0);vec3 farPoint=(cameraWorld*vec4(view.xyz/view.w,1.0)).xyz;vec3 ray=farPoint-eye;return eye+ray*((facePlane.w-dot(facePlane.xyz,eye))/dot(facePlane.xyz,ray));}
vec2 node(vec2 p){vec4 c=texture2D(packedGrid,(p+0.5)/size);float q=floor(c.r*255.0+0.5)+256.0*floor(c.g*255.0+0.5);return vec2(q>=32768.0?q-65536.0:q,floor(c.b*255.0+0.5));}
vec2 sampleValue(){vec3 p=fragmentPoint();float lon=degrees(atan(-p.z,p.x)),lat=degrees(atan(p.y,length(p.xz)));
vec2 q=vec2(mod(lon+180.0,360.0)*2.0,clamp((90.0-lat)*2.0,0.0,360.0));
vec2 lo=floor(q),hi=vec2(mod(lo.x+1.0,size.x),min(lo.y+1.0,size.y-1.0)),f=fract(q);
vec2 a=node(lo),b=node(vec2(hi.x,lo.y)),c=node(vec2(lo.x,hi.y)),d=node(hi);
vec4 w=vec4((1.0-f.x)*(1.0-f.y),f.x*(1.0-f.y),(1.0-f.x)*f.y,f.x*f.y);
float mask=0.0;if(w.x>0.0)mask=max(mask,a.y);if(w.y>0.0)mask=max(mask,b.y);if(w.z>0.0)mask=max(mask,c.y);if(w.w>0.0)mask=max(mask,d.y);
return vec2(dot(vec4(a.x,b.x,c.x,d.x),w),mask);}
void main(){vec2 s=sampleValue();if(diagnostic==1){float q=floor(s.x+32768.0+0.5);gl_FragColor=vec4(floor(q/256.0)/255.0,mod(q,256.0)/255.0,s.y/255.0,1.0);return;}
if(s.y>0.0)discard;float t=clamp((s.x*scale+offset-273.15+80.0)/120.0,0.0,1.0);
vec3 cold=vec3(0.24,0.15,0.72),middle=vec3(0.20,0.75,0.87),hot=vec3(0.94,0.25,0.14);
vec3 color=t<0.5?mix(cold,middle,t*2.0):mix(middle,hot,(t-0.5)*2.0);gl_FragColor=vec4(color,0.45);}`;
