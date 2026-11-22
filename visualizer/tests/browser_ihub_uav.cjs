// Run against the local preview with the retained I-HUB preset and payloads.
const fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const {default:p}=await import(process.env.PUPPETEER_MODULE||'puppeteer-core');
 const b=await p.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface']});
 try{
  const page=await b.newPage(),errors=[];await page.setViewport({width:1280,height:720});
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('favicon'))errors.push(m.text())});
  page.on('response',r=>{if(r.status()>=400&&!r.url().includes('favicon'))errors.push(`${r.status()} ${r.url()}`)});
  await page.goto(process.argv[2]||'http://127.0.0.1:8823/canopy/viewer/3d/?scene=imperial_corridor_8km');
  await page.waitForFunction(()=>window.viewer&&document.querySelector('#loading').classList.contains('hide'),{timeout:240000});
  const pause=ms=>new Promise(r=>setTimeout(r,ms));
  const choose=async name=>{await page.click(`[data-shot="${name}"]`);await pause(3200)};
  const targetVisible=()=>page.evaluate(()=>{let result;cityDetailTiles.group.traverse(o=>{if(o.userData.sourceAsset===viewer.SCENE.interior.replace_asset)result=o.visible});return result});
  assert.equal(await page.evaluate(()=>viewer.uavs.group.visible),false);
  const shots=await page.$$eval('[data-shot]',els=>els.map(e=>e.dataset.shot));assert.equal(shots.indexOf('interior'),shots.indexOf('whiteCity')+1);
  await choose('whiteCity');
  let recorder;
  if(process.env.CANOPY_RECORD)recorder=await page.screencast({path:process.env.CANOPY_RECORD,format:'webm',fps:24,ffmpegPath:process.env.FFMPEG_PATH});
  await pause(2000);await choose('interior');
  if(await page.evaluate(()=>ihubInterior.journey?.playing))await page.click('#play');
  await page.$eval('#step',e=>{e.value=4;e.dispatchEvent(new Event('input',{bubbles:true}))});
  assert.equal(await targetVisible(),false);
  assert(await page.evaluate(()=>ihubInterior.group.visible&&!corridorTerrain.enabled&&cityDetailTiles.loaded.length===64&&viewer.camera.near===.1));
  assert.equal(await page.$eval('#play',e=>e.disabled),false);
  assert(await page.evaluate(()=>ihubInterior.group.getObjectByName('Retained v10 continuous ceiling')?.visible));
  assert(await page.evaluate(()=>{const p=viewer.camera.position;return Math.abs(p.y-(viewer.SCENE.interior.floor_m+1.68))<.01 && !ihubInterior.building.children.some(o=>o.material?.clippingPlanes?.length)}));
  await page.screenshot({path:'cache/white-city-interior/interior-verified.png'});await pause(4000);
  await choose('uavs');
  assert.equal(await targetVisible(),true);
  assert(await page.evaluate(()=>{const d=viewer.camera.position.clone().sub(viewer.controls.target);return viewer.uavs.group.visible&&!ihubInterior.group.visible&&d.y>0&&Math.hypot(d.x,d.z)/d.y<.001}));
  await page.screenshot({path:'cache/white-city-interior/uav-verified.png'});await pause(4500);
  await choose('overview');assert.equal(await page.evaluate(()=>viewer.uavs.group.visible),false);
  assert(await page.evaluate(()=>corridorTerrain.enabled&&viewer.camera.near===5));
  await pause(1500);if(recorder)await recorder.stop();
  await page.setViewport({width:1024,height:768});await choose('uavs');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert(await page.evaluate(()=>{const c=viewer.camera,t=viewer.controls.target;const height=c.position.y-t.y;return 2*height*Math.tan(c.fov*Math.PI/360)>=8000 && 2*height*Math.tan(c.fov*Math.PI/360)*c.aspect>=8000}));
  assert(await page.evaluate(()=>{const d=viewer.camera.position.clone().sub(viewer.controls.target);return Math.hypot(d.x,d.z)/d.y<.001}));
  await choose('traffic');assert.equal(await page.evaluate(()=>viewer.uavs.group.visible),false);
  assert(await page.evaluate(()=>corridorContext.nativeTraffic&&corridorContext.playing&&cityDetailTiles.group.visible));
  assert.deepEqual(errors,[]);fs.writeFileSync('cache/white-city-interior/verification.json',JSON.stringify({passed:true,shots,errors,checks:['default UAV hidden','widget order','interior loads','target shell replaced and restored','64 city tiles retained','interior presentation clock','UAV entire 8 km square top-down desktop/tablet','interior eye height and intact shell','UAV hidden on exit','terrain restored','traffic regression']},null,2));console.log('PASS');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
