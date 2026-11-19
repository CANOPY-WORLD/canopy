// Compare real landscape attributes against a reference build, including the
// main-thread fallback. Continuous software rendering is paused during hashing.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer-core');

(async () => {
  const [referenceURL, candidateURL] = process.argv.slice(2);
  if (!referenceURL || !candidateURL) throw Error('Provide reference and candidate Pages base URLs.');
  const browser = await puppeteer.launch({executablePath:process.env.CHROME_PATH || '/opt/google/chrome/chrome',
    headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
  const results = [];
  try {
    for (const [name, base, fallback] of [['reference',referenceURL,false],['worker',candidateURL,false],['fallback',candidateURL,true]]) {
      const page = await browser.newPage(), errors=[];
      page.setDefaultTimeout(120000);
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {if(message.type()==='error')errors.push(message.text());});
      if(fallback) await page.evaluateOnNewDocument(() => {window.Worker=undefined;});
      await page.goto(new URL('viewer/3d/?scene=imperial_corridor_8km&lite=1&fields=0&shot=overview&play=0',base).href,{waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>!!window.viewer);
      await page.evaluate(()=>{viewer.renderer.render=()=>{};});
      await page.waitForFunction(()=>!!window.corridorContext);
      const result = await page.evaluate(async () => {
        const attributes=[];
        for(const mesh of corridorContext.ground.children) {
          for(const variant of ['flatGeometry','terrainGeometry']) {
            for(const [name,attribute] of Object.entries(mesh.userData[variant].attributes)) {
              const hash=await crypto.subtle.digest('SHA-256',attribute.array);
              attributes.push({layer:mesh.name,variant,name,count:attribute.count,bytes:attribute.array.byteLength,
                sha256:Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('')});
            }
          }
        }
        attributes.sort((a,b)=>`${a.layer}/${a.variant}/${a.name}`.localeCompare(`${b.layer}/${b.variant}/${b.name}`));
        return {mode:corridorContext.ground.userData.preparation||'original-main-thread',attributes};
      });
      assert.deepEqual(errors,[]);
      if(name!=='reference') {
        assert.equal(result.mode,fallback?'main-thread':'worker');
        assert.deepEqual(result.attributes,results[0].attributes,'Every position, height and normal must retain identical bytes');
      }
      results.push({name,...result,errors});
      console.log(`${name}: ${result.attributes.length} attribute hashes verified (${result.mode})`);
      await page.close();
    }
    fs.mkdirSync('cache/qa/ground-equivalence',{recursive:true});
    fs.writeFileSync('cache/qa/ground-equivalence/results.json',JSON.stringify({passed:true,continuousRenderingPaused:true,results},null,2)+'\n');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
