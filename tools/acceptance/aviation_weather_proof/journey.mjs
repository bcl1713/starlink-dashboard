/** Diagnostic overlays in the real Overview renderer, using provisioned CDP. */
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {resolve,dirname} from 'node:path';
import {writeFileSync} from 'node:fs';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(resolve(root,'frontend/mission-planner/package.json'));
const {chromium}=require('@playwright/test'),{buildSync}=require('esbuild');
const args=Object.fromEntries(process.argv.slice(2).reduce((rows,v,i,all)=>i%2?rows:[...rows,[v.slice(2),all[i+1]]],[]));
const output=args.artifacts,requests=[],errors=[];
const save=(name,value)=>writeFileSync(resolve(output,name),JSON.stringify(value,null,2));
const result={status:'failed',native_overview:false,samples:{},metrics:[],captures:[],controls:{}};
const browser=await chromium.connectOverCDP(args.session);let context;
try{
 context=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:1});
 const request=context.request;
 const waypointTime=offset=>new Date(Date.now()+offset).toISOString().replace('T',' ').slice(0,19)+'Z';
 const mission='aviation-proof',leg='diagnostic-route';
 const created=await request.post(`${args.origin}/api/v2/missions`,{data:{id:mission,name:'Aviation proof route fixture',legs:[{id:leg,name:'Diagnostic route',route_id:'aviation-proof-route',transports:{initial_x_satellite_id:'X-1'}}]}});
 if(!created.ok())throw Error(`seed mission ${created.status()} ${await created.text()}`);
 const kml=`<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Aviation diagnostic route</name><Placemark><name>Diagnostic departure</name><description>Time Over Waypoint: ${waypointTime(-600000)}</description><Point><coordinates>-104,35,10000</coordinates></Point></Placemark><Placemark><name>Diagnostic arrival</name><description>Time Over Waypoint: ${waypointTime(1800000)}</description><Point><coordinates>-98,35,10000</coordinates></Point></Placemark><Placemark><name>Diagnostic route</name><LineString><coordinates>-104,35,10000 -102,35,10000 -100,35,10000 -98,35,10000</coordinates></LineString></Placemark></Document></kml>`;
 const uploaded=await request.put(`${args.origin}/api/v2/missions/${mission}/legs/${leg}/route`,{multipart:{file:{name:'aviation-proof.kml',mimeType:'application/vnd.google-earth.kml+xml',buffer:Buffer.from(kml)}}});
 if(!uploaded.ok())throw Error(`seed route ${uploaded.status()} ${await uploaded.text()}`);save('seeded-route.json',await uploaded.json());
 const activated=await request.post(`${args.origin}/api/v2/missions/${mission}/legs/${leg}/activate`);if(!activated.ok())throw Error(`activate route ${activated.status()} ${await activated.text()}`);
 const page=await context.newPage();page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',route=>{const url=new URL(route.request().url());const allowed=url.origin===args.origin||['data:','blob:'].includes(url.protocol);requests.push({url:url.href,allowed,method:route.request().method()});return allowed?route.continue():route.abort();});
 await page.addInitScript(()=>{const roots=[];Object.assign(window,{__overviewEvidenceRoots:roots,__REACT_DEVTOOLS_GLOBAL_HOOK__:{supportsFiber:true,inject:()=>1,onCommitFiberRoot:(_id,root)=>{if(!roots.includes(root))roots.push(root);},onCommitFiberUnmount:()=>{},onPostCommitFiberRoot:()=>{},checkDCE:()=>{}}});});
 await page.goto(`${args.origin}/overview`,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__overviewEvidenceRoots?.some(r=>r.containerInfo?.getState?.().gl.domElement.isConnected),null,{timeout:60000});
 const built=buildSync({entryPoints:[resolve(root,'frontend/mission-planner/tests/e2e/support/aviation-weather-proof/runtime.ts')],bundle:true,write:false,format:'iife',define:{'process.env.NODE_ENV':'"production"'}});
 await page.addScriptTag({content:built.outputFiles[0].text});result.native_overview=true;result.initial=await page.evaluate(()=>window.aviationProof.snapshot());
 const install=async(source)=>{await page.evaluate(source=>window.aviationProof.install(`/api/overview-weather/aviation-proof-assets/${source}/descriptor.json`),source);result.metrics.push(await page.evaluate(()=>window.aviationProof.snapshot()));};
 const capture=async(name,lat,lon,radius=5)=>{await page.evaluate(([a,b,r])=>window.aviationProof.look(a,b,r),[lat,lon,radius]);await page.waitForTimeout(150);const path=`${name}.png`;await page.screenshot({path:resolve(output,path)});result.captures.push(path);(result.views??=[]).push({path,...await page.evaluate(()=>window.aviationProof.snapshot())});};
 await install('gfs');
 const gfs=[[0,-180],[10,179.5],[-10,-179.5],[89,0],[-89,120],[70,-60],[-70,30],[50,-45],[-35,135],[20,30]];
 result.samples.gfs=[];for(const [lat,lon]of gfs)result.samples.gfs.push(await page.evaluate(([a,b])=>window.aviationProof.sample(a,b),[lat,lon]));
 for(const [name,lat,lon,r]of [['model-world',20,-30,7],['model-north-atlantic',50,-40,4],['model-antimeridian',5,180,5],['model-polar',85,0,5],['model-desktop',35,-100,5]])await capture(name,lat,lon,r);
 await page.getByRole('button',{name:'Enter fullscreen overview',exact:true}).click();await capture('model-fullscreen',35,-100);await page.evaluate(()=>document.exitFullscreen());
 await page.setViewportSize({width:390,height:844});await capture('model-mobile',35,-100);await page.setViewportSize({width:1920,height:1080});
 await install('isigmet');result.advisory_label=await page.locator('[data-aviation-proof]').innerText();await capture('advisory-victor6',15,166,4.5);await capture('advisory-route-aircraft-station',35,-100);await capture('advisory-world',10,100,7);
 await install('goes19-c13');result.satellite_label=await page.locator('[data-aviation-proof]').innerText();result.samples['goes19-c13']=[];
 for(const [lon,lat]of [[-75,0],[-80,10],[-100,20],[-60,30],[-90,40],[-50,-10],[-65,-25],[-100,-30],[-120,5],[-35,15]])result.samples['goes19-c13'].push(await page.evaluate(([a,b])=>window.aviationProof.sample(a,b),[lat,lon]));
 for(const [name,lat,lon,r]of [['satellite-americas',5,-75,5],['satellite-atlantic-limb',10,-25,5],['satellite-night',0,-75,6]]){if(name==='satellite-night')await page.evaluate(()=>window.aviationProof.night(true));await capture(name,lat,lon,r);await page.evaluate(()=>window.aviationProof.night(false));}
 await install('synthetic');const controls=[];for(const [lat,lon]of [[0,179.75],[89.5,0],[-89.5,0],[0,0]])controls.push(await page.evaluate(([a,b])=>window.aviationProof.sample(a,b),[lat,lon]));
 result.synthetic_samples=controls;result.controls.seam=controls[0].mask===0&&Math.abs(controls[0].value-controls[0].cpu.value)<=.01;result.controls.poles=controls.slice(1,3).every(s=>s.mask===0&&Math.abs(s.value-s.cpu.value)<=.01);result.controls.invalid=controls[3].mask===3&&controls[3].value===null;
 const before=await page.evaluate(()=>window.aviationProof.snapshot());try{await install('missing');}catch{}const after=await page.evaluate(()=>window.aviationProof.snapshot());result.controls.failed_install_ownership=JSON.stringify(before.allocation.current)===JSON.stringify(after.allocation.current)&&before.label===after.label;
 // CPU geometry controls exercise the same native objects; GPU controls above
 // remain separately labeled from these deterministic shape/direction controls.
 const synthetic=buildSync({stdin:{contents:`import {active,advisoryMesh} from './tests/e2e/support/aviation-weather-proof/advisory-renderer';import {barb} from './tests/e2e/support/aviation-weather-proof/sampling';import {labels} from './tests/e2e/support/aviation-weather-proof/model';import * as THREE from 'three';import {earthPoint} from './tests/e2e/support/aviation-weather-proof/grid-renderer';const feature={id:'synthetic-hole',geometry:{type:'Polygon',coordinates:[[[-10,-10],[10,-10],[10,10],[-10,10],[-10,-10]],[[-2,-2],[-2,2],[2,2],[2,-2],[-2,-2]]]},properties:{validity:{start_ms:0,end_ms:10},cancellation:{cancelled:false},status:'active'}};const release=window.aviationProof.reserveControlGeometry(4800000);const object=advisoryMesh([feature],5);object.mesh.updateMatrixWorld(true);const ray=(lat,lon)=>{const p=earthPoint(lat,lon,5);return new THREE.Raycaster(p,p.clone().normalize().negate()).intersectObject(object.mesh).length;};window.syntheticControls={holes:ray(0,0)===0&&ray(5,5)>0,expiry:!active(feature,10),cancelled:!active({...feature,properties:{...feature.properties,cancellation:{cancelled:true}}},5),directional:barb(10,0).fromEast===-1&&barb(10,0).knots===20,asynchronous:labels({region_intervals:[{region:'A',scan_start_ms:0,scan_end_ms:1000},{region:'B',scan_start_ms:2000,scan_end_ms:3000}]}).includes('B: 1970-01-01T00:00:02.000Z')};object.dispose();const seamFeature={...feature,geometry:{type:'MultiPolygon',coordinates:[[[[175,-5],[180,-5],[180,5],[175,5],[175,-5]]],[[[-180,-5],[-175,-5],[-175,5],[-180,5],[-180,-5]]]]}};const seam=advisoryMesh([seamFeature],5);seam.mesh.updateMatrixWorld(true);const hits=lon=>{const p=earthPoint(0,lon,5);return new THREE.Raycaster(p,p.clone().normalize().negate()).intersectObject(seam.mesh).length;};window.syntheticControls.advisory_dateline=hits(178)>0&&hits(-178)>0&&hits(0)===0;seam.dispose();release();`,resolveDir:resolve(root,'frontend/mission-planner')},bundle:true,write:false,format:'iife'});
 await page.addScriptTag({content:synthetic.outputFiles[0].text});Object.assign(result.controls,await page.evaluate(()=>window.syntheticControls));
 const racing=await page.evaluate(async()=>{const first=window.aviationProof.install('/api/overview-weather/aviation-proof-assets/gfs/descriptor.json');const last=window.aviationProof.install('/api/overview-weather/aviation-proof-assets/goes19-c13/descriptor.json');const results=await Promise.allSettled([first,last]);return {states:results.map(r=>r.status),snapshot:window.aviationProof.snapshot()};});
 result.controls.asynchronous_ownership=racing.states[0]==='rejected'&&racing.states[1]==='fulfilled'&&racing.snapshot.label.includes('noaa-goes19');result.race=racing;
 await page.evaluate(()=>window.aviationProof.dispose());result.restored=await page.evaluate(()=>window.aviationProof.snapshot());result.controls.camera_restored=result.metrics[0].savedView.every((v,i)=>Math.abs(v-result.restored.camera.position[i])<1e-5);result.errors=errors;result.status=errors.length===0&&Object.values(result.controls).every(Boolean)?'passed':'failed';
}catch(error){result.error=String(error);throw error;}finally{save('journey.json',result);save('requests.json',requests);await context?.close();await browser.close();}
