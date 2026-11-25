// Synthetic browser fixture exercises actual Three.js camera and retained-mesh collision.
import assert from 'node:assert/strict';
const {default:puppeteer} = await import(process.env.PUPPETEER_MODULE);
const browser = await puppeteer.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
try {
  const page = await browser.newPage();
  await page.goto((process.argv[2] ?? 'http://127.0.0.1:8876') + '/viewer/3d/navigation.js');
  await page.setContent('<canvas></canvas><input id="text"><script type="importmap">{"imports":{"three":"/vendor/three/build/three.module.js"}}</script>');
  const result = await page.evaluate(async () => {
    const THREE = await import('three');
    const {createNavigation} = await import('/viewer/3d/navigation.js');
    const camera = new THREE.PerspectiveCamera(45,1,5,1000);camera.position.set(0,1.6,0);
    const controls = {target:new THREE.Vector3(0,1.6,-10),enabled:true,update(){}};
    const room = new THREE.Group();
    const wall = new THREE.Mesh(new THREE.BoxGeometry(10,3,.1),new THREE.MeshBasicMaterial());wall.position.set(0,1.5,-2);room.add(wall);
    let indoors = true;
    const nav = createNavigation({camera,controls,canvas:document.querySelector('canvas'),indoorRoot:()=>indoors?room:null,groundHeight:()=>0,invalidate(){},onEnter(){}});
    const key = (type,code,target=window) => target.dispatchEvent(new KeyboardEvent(type,{code,bubbles:true,cancelable:true}));
    nav.setActive(true); key('keydown','KeyW'); for(let i=0;i<100;i++)nav.tick(.05);key('keyup','KeyW');
    const blockedZ=camera.position.z, indoorY=camera.position.y;
    key('keydown','KeyE');nav.tick(.05);key('keyup','KeyE');const noFly=camera.position.y===indoorY;
    const pos=camera.position.clone();key('keydown','KeyD',document.querySelector('input'));nav.tick(.05);const typing=pos.equals(camera.position);
    key('keydown','KeyD');window.dispatchEvent(new Event('blur'));nav.tick(.05);const blur=pos.equals(camera.position);
    key('keydown','Escape');const exited=!nav.active&&nav.manual&&controls.enabled;
    nav.reset(); const reset=!nav.manual;
    indoors=false;camera.position.set(0,20,0);nav.setActive(true);key('keydown','KeyW');nav.tick(.05);key('keyup','KeyW');const city=camera.position.z<0;
    key('keydown','KeyE');nav.tick(.05);key('keyup','KeyE');const ascend=camera.position.y>20;
    nav.reset();return {blockedZ,noFly,typing,blur,exited,reset,city,ascend,near:camera.near};
  });
  assert.ok(result.blockedZ > -1.7 && result.blockedZ < -1, JSON.stringify(result));
  for(const k of ['noFly','typing','blur','exited','reset','city','ascend'])assert.equal(result[k],true,k);
  assert.equal(result.near,5);
  console.log('PASS',JSON.stringify(result));
} finally {await browser.close();}
