import test from 'node:test';
import assert from 'node:assert/strict';
import {compileFlow} from '../compile.mjs';
import {toGoogleSlidesRequests} from '../adapters/google-slides.mjs';
import {readBox,auditGoogleSlidesReadback} from '../adapters/google-slides-readback.mjs';

const profile={schema:'slide-flow-style/v1',id:'SyntheticStyle',version:'1',colors:{
 canvas:'#061423',panel:'#081B30',ink:'#F8FAFF',muted:'#A5C4E1',action:'#2AD4EC',secondary:'#B69AF3',gate:'#FFAE53',verified:'#43DDB5'}};
const graph={schema:'slide-flow-graph/v1',id:'SyntheticB',eyebrow:'SYNTHETIC',
title:'Run a reliable workflow',qualifier:'NO PRODUCTION DATA',
lanes:[{id:'a',title:'TEST FLOW',steps:[
  {id:'a',kind:'source',proof_state:'neutral',title:'Source',summary:'Read source',action:{label:'OPEN SOURCE',url:'https://example.org/source'}},
  {id:'b',kind:'gate',proof_state:'unverified',title:'Evidence',summary:'Result pending'}
],edges:[{from:'a',to:'b',kind:'conditional'}]}]};
function syntheticReadback(plan){
 const pageElements=[],updates=new Map(plan.requests.filter(x=>x.updateTextStyle).map(x=>[x.updateTextStyle.objectId,x.updateTextStyle.style]));
 for(const r of plan.requests.filter(x=>x.createShape)){
  const shape=r.createShape,p=shape.elementProperties,t=p.transform,s=p.size;
  const style=updates.get(shape.objectId),texts=style?[{textRun:{content:'example',style}}]:[];
  pageElements.push({objectId:shape.objectId,
   size:{width:{magnitude:3000000,unit:'EMU'},height:{magnitude:3000000,unit:'EMU'}},
   transform:{scaleX:s.width.magnitude*12700/3000000,scaleY:s.height.magnitude*12700/3000000,translateX:t.translateX*12700,translateY:t.translateY*12700,unit:'EMU'},
   shape:{shapeType:shape.shapeType,text:{textElements:texts}}});
 }
 return {slides:[{objectId:plan.slide_id,pageElements}]};
}
const plan=toGoogleSlidesRequests(compileFlow(graph,profile),'synthetic_page_01');
test('Google normalizes shape size but preserves effective bounds',()=>{
  const el={size:{width:{magnitude:3000000,unit:'EMU'},height:{magnitude:3000000,unit:'EMU'}},transform:{scaleX:.6096,scaleY:.4318,translateX:304800,translateY:1473200,unit:'EMU'}};
  assert.deepEqual(readBox(el),{x:24,y:116,w:144,h:102});
});
test('correct native object IDs, text links and geometry accept structurally',()=>{
  const receipt=auditGoogleSlidesReadback(syntheticReadback(plan),plan);
  assert.equal(receipt.state,'STRUCTURAL_READBACK_ACCEPTED');
  assert.equal(receipt.faults.length,0);
  assert.equal(receipt.links_checked,1);
  assert.equal(receipt.arrows_checked,1);
  assert.equal(receipt.visual_state,'NOT_VISUALLY_INSPECTED');
  assert.equal(receipt.interaction_state,'NOT_BROWSER_CLICK_TESTED');
});
test('missing linked text fails closed',()=>{
  const snapshot=syntheticReadback(plan);
  const linked=snapshot.slides[0].pageElements.find(x=>x.shape.text.textElements.some(t=>t.textRun.style.link));
  linked.shape.text.textElements[0].textRun.style.link.url='https://example.org/wrong';
  assert.match(auditGoogleSlidesReadback(snapshot,plan).faults.join(),/missing\/mismatched live link/);
});
test('under-9-point labels are rejected',()=>{
  const snapshot=syntheticReadback(plan);
  snapshot.slides[0].pageElements.find(x=>x.shape.text.textElements.length).shape.text.textElements[0].textRun.style.fontSize.magnitude=7.8;
  assert.match(auditGoogleSlidesReadback(snapshot,plan).faults.join(),/small text/);
});
test('geometry movement and missing nodes fail closed',()=>{
  const snapshot=syntheticReadback(plan);snapshot.slides[0].pageElements[0].transform.translateX+=127000;
  assert.match(auditGoogleSlidesReadback(snapshot,plan).faults.join(),/geometry drift/);
  snapshot.slides[0].pageElements.shift();
  assert.match(auditGoogleSlidesReadback(snapshot,plan).faults.join(),/missing object/);
});
