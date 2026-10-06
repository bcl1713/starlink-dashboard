import { MERCATOR_LIMIT } from './weather-projection';
export const weatherFragmentShader = `
  uniform sampler2D radarTexture;
  uniform sampler2D coverageTexture;
  uniform sampler2D detailRadar;
  uniform sampler2D detailCoverage;
  uniform vec4 detailBounds[8];
  uniform vec4 detailRects[8];
  uniform float detailValid[8];
  uniform float detailFades[8];
  varying vec3 vWeatherPosition;
  vec2 slotUv(vec2 uv, int slot) {
    vec4 b = detailBounds[slot];
    return detailRects[slot].xy + clamp((uv-b.xy)/(b.zw-b.xy),0.0,1.0)*detailRects[slot].zw;
  }
  vec4 coveredRain(vec4 rain, float absent) {
    return vec4(rain.rgb*rain.a, rain.a)*(1.0-absent);
  }
  void main() {
    vec3 p = normalize(vWeatherPosition);
    float latitude = asin(clamp(p.y,-1.0,1.0));
    float longitude = atan(-p.z,p.x);
    float absent = 1.0;
    vec4 rain = vec4(0.0);
    if (abs(latitude) <= ${MERCATOR_LIMIT}) {
      vec2 uv = vec2(fract(longitude/6.28318530718+0.5),
        clamp(0.5-log(tan(0.78539816339+latitude/2.0))/6.28318530718,0.0,1.0));
      absent = texture2D(coverageTexture,uv).a;
      rain = coveredRain(texture2D(radarTexture,uv),absent);
      for (int i=0; i<8; i++) {
        vec4 b = detailBounds[i];
        if (detailValid[i] < 0.5 || any(lessThan(uv,b.xy)) || any(greaterThanEqual(uv,b.zw))) continue;
        vec2 size = b.zw-b.xy;
        vec2 edge = size/510.0;
        vec4 distances = vec4(uv.x-b.x,b.z-uv.x,uv.y-b.y,b.w-uv.y);
        vec4 weights = smoothstep(vec4(0.0),vec4(edge.x,edge.x,edge.y,edge.y),distances);
        float mask = texture2D(detailCoverage,slotUv(uv,i)).a;
        // Eligible adjacent slots remove the fallback seam. Their absence
        // masks remain conservative within one texel of the shared boundary.
        for (int j=0; j<8; j++) {
          if (i==j || detailValid[j]<0.5 || detailFades[j]<0.999) continue;
          vec4 c = detailBounds[j];
          bool sameRow = abs(c.y-b.y)<0.000001 && abs(c.w-b.w)<0.000001;
          bool sameCol = abs(c.x-b.x)<0.000001 && abs(c.z-b.z)<0.000001;
          bool left = sameRow && (abs(c.z-b.x)<0.000001 || abs(c.z-b.x-1.0)<0.000001);
          bool right = sameRow && (abs(c.x-b.z)<0.000001 || abs(c.x-b.z+1.0)<0.000001);
          bool top = sameCol && abs(c.w-b.y)<0.000001;
          bool bottom = sameCol && abs(c.y-b.w)<0.000001;
          if (left) weights.x=1.0;
          if (right) weights.y=1.0;
          if (top) weights.z=1.0;
          if (bottom) weights.w=1.0;
          if ((left && distances.x<edge.x) || (right && distances.y<edge.x) || (top && distances.z<edge.y) || (bottom && distances.w<edge.y)) {
            vec2 nearUv=uv;
            if(left && c.z>b.x+0.5)nearUv.x+=1.0;
            if(right && c.x<b.z-0.5)nearUv.x-=1.0;
            mask=max(mask,texture2D(detailCoverage,slotUv(nearUv,j)).a);
          }
        }
        float blend = min(min(weights.x,weights.y),min(weights.z,weights.w))*detailFades[i];
        vec4 detail = coveredRain(texture2D(detailRadar,slotUv(uv,i)),mask);
        rain = mix(rain,detail,blend);
        absent = blend>=0.999 ? mask : max(absent,mask);
        break;
      }
    }
    float hatch = 1.0-step(1.5,mod(gl_FragCoord.x+gl_FragCoord.y,12.0));
    float hatchAlpha = absent*hatch*0.17;
    float alpha = rain.a*0.40+hatchAlpha;
    if(alpha<=0.001)discard;
    vec3 color=(rain.rgb*0.40+vec3(0.42)*hatchAlpha)/alpha;
    gl_FragColor=vec4(color,alpha);
    #include <colorspace_fragment>
  }
`;
