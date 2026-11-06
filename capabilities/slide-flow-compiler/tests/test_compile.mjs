import test from 'node:test';
import assert from 'node:assert/strict';
import {compileFlow,checkGraph,auditIR} from '../compile.mjs';
import {toGoogleSlidesRequests} from '../adapters/google-slides.mjs';

const profile = {schema:'slide-flow-style/v1',id:'SyntheticNeon',version:'1',
  colors:{canvas:'#061423',panel:'#081B30',ink:'#F8FAFF',muted:'#A5C4E1',
    action:'#2AD4EC',secondary:'#B69AF3',gate:'#FFAE53',verified:'#43DDB5'}};
const graph = {schema:'slide-flow-graph/v1',id:'SyntheticA',
  eyebrow:'OPERATIONS / SYNTHETIC',title:'Dispatch to verification',
  qualifier:'SYNTHETIC CASE — NO ACTUAL ORGANIZATION DATA',
  lanes:[
    {id:'delivery',title:'WORKFLOW',steps:[
      {id:'origin',kind:'source',proof_state:'neutral',title:'Authoritative source',summary:'Review the canonical source',action:{label:'SOURCE',url:'https://example.org/source'}},
      {id:'work',kind:'action',proof_state:'pending',title:'Field work',summary:'Observed work not verified',action:{label:'WORK DETAILS',url:'https://example.org/work'}},
      {id:'gate',kind:'gate',proof_state:'unverified',title:'Evidence gate',summary:'Need before and after proof',action:{label:'EVIDENCE RULES',url:'https://example.org/rules'}},
      {id:'draft',kind:'action',proof_state:'pending',title:'Review draft',summary:'Do not claim sent yet',action:{label:'OPEN DRAFT',url:'https://example.org/draft'}}
    ],edges:[{from:'origin',to:'work',kind:'sequence'},{from:'work',to:'gate',kind:'sequence'},{from:'gate',to:'draft',kind:'conditional'}]},
    {id:'parallel',title:'INDEPENDENT DEVICE CAMPAIGN',steps:[
      {id:'fleet',kind:'source',proof_state:'neutral',title:'Fleet baseline',summary:'Device candidates not tickets'},
      {id:'authorization',kind:'gate',proof_state:'unverified',title:'Management access',summary:'Proof of authorization required'},
      {id:'trial',kind:'action',proof_state:'pending',title:'Controlled pilot',summary:'Requires actual observed test'}
    ],edges:[{from:'fleet',to:'authorization',kind:'sequence'},{from:'authorization',to:'trial',kind:'conditional'}]}
  ],footer:'VERIFY SOURCE → REVIEW EVIDENCE → SEND ONLY AFTER PROOF'};

const clone = x => JSON.parse(JSON.stringify(x));

test('deterministic output with unique element identifiers and safe geometry', () => {
  const a=compileFlow(graph,profile), b=compileFlow(graph,profile);
  assert.deepEqual(a,b);
  assert.deepEqual(auditIR(a),[]);
  assert.equal(new Set(a.objects.map(o=>o.id)).size,a.objects.length);
  assert.equal(a.objects.filter(o=>o.type==='arrow').length,5);
  assert.equal(a.proof_ceiling,'COMPILED_GEOMETRY_ONLY');
});
test('actual clickable labels and native arrow shapes compile',()=>{
  const plan=toGoogleSlidesRequests(compileFlow(graph,profile),'synthetic_slide_a');
  assert.equal(plan.proof_ceiling,'REQUESTS_COMPILED_NOT_PUBLISHED');
  assert.equal(plan.requests.filter(x=>x.createShape?.shapeType==='RIGHT_ARROW').length,5);
  const links=plan.requests.filter(x=>x.updateTextStyle?.style?.link?.url);
  assert.equal(links.length,4);
  assert.ok(links.every(x=>x.updateTextStyle.style.link.url.startsWith('https://')));
  assert.ok(plan.requests.some(x=>x.createShape?.shapeType==='ROUND_RECTANGLE'));
});
test('parallel relationships generate zero implied arrows',()=>{
  const g=clone(graph);g.lanes[1].edges=[];
  assert.equal(compileFlow(g,profile).objects.filter(o=>o.type==='arrow').length,3);
});
test('false verified state without proof is forbidden',()=>{
  const g=clone(graph);g.lanes[0].steps[2].proof_state='verified';
  assert.ok(checkGraph(g,profile).some(x=>x.includes('proof_url')));
  assert.throws(()=>compileFlow(g,profile));
});
test('unverified outcome is forbidden',()=>{
  const g=clone(graph);g.lanes[0].steps[3].kind='outcome';
  assert.ok(checkGraph(g,profile).some(x=>x.includes('outcome requires')));
});
test('unknown source action and overly dense copy rejected',()=>{
  const g=clone(graph);g.lanes[0].steps[0].action.url='javascript:alert(1)';
  g.lanes[0].steps[1].summary='a'.repeat(200);
  const errors=checkGraph(g,profile);
  assert.ok(errors.some(x=>x.includes('https')));
  assert.ok(errors.some(x=>x.includes('summary')));
});
test('graph works with an independent alternate profile',()=>{
  const bright=clone(profile);bright.id='BrightProfile';bright.colors.canvas='#FFFFFF';bright.colors.panel='#EFF7FD';
  const a=compileFlow(graph,bright);
  assert.equal(a.style_id,'BrightProfile');
  assert.deepEqual(auditIR(a),[]);
});
test('fail closed on fifth card in a lane',()=>{
  const g=clone(graph);g.lanes[0].steps.push({...g.lanes[0].steps[0],id:'fifth'});
  assert.ok(checkGraph(g,profile).some(x=>x.includes('1-4 steps')));
});


test('card actions stay clear of descriptions and borders in both row heights',()=>{
  const g=clone(graph);
  g.lanes[1].steps[0].action={label:'OPEN SOURCE',url:'https://example.org/fleet'};
  const plan=toGoogleSlidesRequests(compileFlow(g,profile),'synthetic_slide_clearance');
  const objects=new Map(plan.requests.filter(x=>x.createShape).map(x=>[x.createShape.objectId,x.createShape.elementProperties]));
  for(const [id,props] of objects){
    if(!id.endsWith('_action'))continue;
    const stem=id.slice(0,-'_action'.length),desc=objects.get(stem+'_description'),panel=objects.get(stem+'_panel');
    assert.ok(desc && panel,'every action belongs to one description and card');
    const actionY=props.transform.translateY,actionH=props.size.height.magnitude;
    const descEnd=desc.transform.translateY+desc.size.height.magnitude;
    const cardEnd=panel.transform.translateY+panel.size.height.magnitude;
    assert.ok(actionY-descEnd>=1,stem+' description-to-link clearance');
    assert.ok(cardEnd-(actionY+actionH)>=8,stem+' bottom margin');
  }
  const inserted=plan.requests.filter(x=>x.insertText).map(x=>x.insertText.text);
  assert.ok(inserted.every(x=>!x.includes('↗')),'textual link glyph must not leak into exported decks');
  assert.ok(plan.requests.some(x=>x.updateTextStyle?.style?.link?.url),'native hyperlinks retained');
});
