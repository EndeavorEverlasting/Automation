/** Structural readback verifier. Does not authenticate provider snapshots or inspect pixels. */

export function readBox(el){
 const sz=el?.size,tr=el?.transform;if(!sz||!tr)throw Error("missing size/transform");
 const pt=(m,u)=>u==="EMU"?m/12700:u==="PT"?m:NaN;
 const x=pt(tr.translateX||0,tr.unit),y=pt(tr.translateY||0,tr.unit),sw=pt(sz.width?.magnitude,sz.width?.unit),sh=pt(sz.height?.magnitude,sz.height?.unit);
 if([x,y,sw,sh,tr.scaleX,tr.scaleY].some(v=>!Number.isFinite(v)))throw Error("invalid geometric unit/scale");
 if(Math.abs(tr.shearX||0)>1e-6||Math.abs(tr.shearY||0)>1e-6)throw Error("sheared object not supported by rectangular QA");
 return {x,y,w:sw*tr.scaleX,h:sh*tr.scaleY};
}

export function auditGoogleSlidesReadback(snapshot,plan,opts={}){
 if(plan?.schema!=="google-slides-batch-update-plan/v1")throw Error("compiled adapter plan required");
 const faults=[],slides=snapshot.slides||[snapshot],slide=slides.find(x=>x.objectId===plan.slide_id);
 if(!slide){return {schema:"google-slides-readback-audit/v1",faults:["target slide missing"],state:"REJECTED",visual_state:"NOT_VISUALLY_INSPECTED"}}
 const actual=new Map((slide.pageElements||[]).map(x=>[x.objectId,x]));
 const expected=(plan.requests||[]).filter(r=>r.createShape).map(r=>r.createShape),linkUpdates=(plan.requests||[]).filter(r=>r.updateTextStyle?.style?.link?.url),sizeTol=opts.size_tolerance_pt??1.0,minFont=opts.min_font_pt??9.0;
 let linksChecked=0,arrows=0,textRunsChecked=0;
 for(const request of expected){
  const act=actual.get(request.objectId);
  if(!act){faults.push("missing object "+request.objectId);continue}
  if(act.shape?.shapeType!==request.shapeType)faults.push("shape type drift "+request.objectId);
  if(request.shapeType==="RIGHT_ARROW"||request.shapeType==="DOWN_ARROW")arrows++;
  try{
   const ab=readBox(act),bb=request.elementProperties,expectedBox={x:bb.transform.translateX,y:bb.transform.translateY,w:bb.size.width.magnitude,h:bb.size.height.magnitude};
   for(const k of ["x","y","w","h"])if(Math.abs(ab[k]-expectedBox[k])>sizeTol)faults.push("geometry drift "+request.objectId+"."+k);
   if(ab.x<-.5||ab.y<-.5||ab.x+ab.w>720.5||ab.y+ab.h>405.5)faults.push("out of canvas "+request.objectId);
  }catch(e){faults.push("cannot measure "+request.objectId+": "+e.message)}
  for(const e of act.shape?.text?.textElements||[]){
   const pt=e.textRun?.style?.fontSize?.magnitude;
   if(pt!==undefined){textRunsChecked++;if(pt<minFont)faults.push("small text "+request.objectId+" "+pt+"pt")}
  }
 }
 for(const update of linkUpdates){
  const id=update.updateTextStyle.objectId,url=update.updateTextStyle.style.link.url,el=actual.get(id);
  if(!el){continue}
  const links=(el.shape?.text?.textElements||[]).map(x=>x.textRun?.style?.link?.url).filter(Boolean);
  if(!links.includes(url))faults.push("missing/mismatched live link "+id);
  else linksChecked++;
 }
 return {schema:"google-slides-readback-audit/v1",state:faults.length?"REJECTED":"STRUCTURAL_READBACK_ACCEPTED",faults,expected_elements:expected.length,observed_elements:actual.size,arrows_checked:arrows,links_checked:linksChecked,text_runs_checked:textRunsChecked,min_font_pt:minFont,visual_state:"NOT_VISUALLY_INSPECTED",interaction_state:"NOT_BROWSER_CLICK_TESTED",provenance:"CALLER_SUPPLIED_SNAPSHOT_NOT_PROVIDER_AUTHENTICATED"};
}
