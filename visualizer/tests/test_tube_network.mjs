import test from 'node:test';
import assert from 'node:assert/strict';
import {clipRoute,selectTubeNetwork} from '../site/viewer/3d/tube-network.mjs';
test('route clipping preserves source bends, depth and fractional endpoints',()=>{
 const path=[[0,0,-10],[3,0,-10],[3,4,-10],[9,4,-10]];
 assert.deepEqual(clipRoute(path,1,9),[[1,0,-10],[3,0,-10],[3,4,-10],[5,4,-10]]);
 assert.deepEqual(path[0],[0,0,-10]);
 for(const [a,b] of [[-1,4],[5,2],[0,20],[0,NaN]])assert.throws(()=>clipRoute(path,a,b));
});
test('select only declared stations and route line; missing connections fail explicitly',()=>{
 const config={line:'p',stations:[{id:'a'},{id:'b'}]};
 const p=(station_id,offset,line='p')=>({id:station_id,station_id,line,direction:'eastbound',s_c_by_pattern:{route:offset}});
 const data={pilot:{platforms:[p('a',1),p('b',7),p('other',9),p('a',2,'other')],patterns:[{id:'route',line:'p',path:[[0,0,-2],[10,0,-2]]}]}};
 const result=selectTubeNetwork(data,config);assert.equal(result.platforms.length,2);assert.equal(result.routes.length,1);assert.deepEqual(result.routes[0].path,[[1,0,-2],[7,0,-2]]);
 assert.throws(()=>selectTubeNetwork(data,{...config,stations:[{id:'missing'}]}));
 data.pilot.patterns=[];assert.throws(()=>selectTubeNetwork(data,config));
});
