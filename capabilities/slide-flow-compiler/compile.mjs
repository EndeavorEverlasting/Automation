/** Portable graph-to-slide IR; no provider/account state. */

export function rgb(hex){if(typeof hex!=="string"||!/^#[0-9a-fA-F]{6}$/.test(hex))throw Error("color must be #RRGGBB");return {red:parseInt(hex.slice(1,3),16)/255,green:parseInt(hex.slice(3,5),16)/255,blue:parseInt(hex.slice(5,7),16)/255};}

export function checkGraph(graph,profile){
 const errors=[],validId=s=>typeof s==="string"&&/^[A-Za-z][A-Za-z0-9_-]{0,15}$/.test(s);
 if(graph?.schema!=="slide-flow-graph/v1")errors.push("schema must be slide-flow-graph/v1");
 if(!validId(graph?.id))errors.push("graph.id invalid");
 for(const [k,max] of [["title",62],["eyebrow",80],["qualifier",100]])if(typeof graph?.[k]!=="string"||!graph[k].trim()||graph[k].length>max)errors.push(k+" missing/too long");
 if(!Array.isArray(graph?.lanes)||graph.lanes.length<1||graph.lanes.length>2)errors.push("lanes must contain 1-2 paths");
 if(profile?.schema!=="slide-flow-style/v1"||!validId(profile?.id))errors.push("explicit style contract required");
 for(const k of ["canvas","panel","ink","muted","action","secondary","gate","verified"])try{rgb(profile?.colors?.[k])}catch{errors.push("invalid style color "+k)}
 const ids=new Set();
 for(const lane of graph?.lanes||[]){
  if(!validId(lane.id)||ids.has(lane.id))errors.push("duplicate/invalid lane.id");ids.add(lane.id);
  if(typeof lane.title!=="string"||lane.title.length>75||!lane.title.trim())errors.push("lane.title missing/too long");
  if(!Array.isArray(lane.steps)||lane.steps.length<1||lane.steps.length>4)errors.push("lane must have 1-4 steps");
  const seen=new Set();
  for(const step of lane.steps||[]){
   if(!validId(step.id)||seen.has(step.id))errors.push("duplicate/invalid step id");seen.add(step.id);
   if(!["source","action","gate","outcome"].includes(step.kind))errors.push("invalid kind");
   if(!["unverified","pending","verified","neutral"].includes(step.proof_state))errors.push("proof state explicit");
   if(step.proof_state==="verified"&&!(step.proof_url&&/^https:\/\//.test(step.proof_url)))errors.push("verified must have actual proof_url");
   if(step.kind==="outcome"&&step.proof_state!=="verified")errors.push("outcome requires verified proof");
   if(typeof step.title!=="string"||!step.title.trim()||step.title.length>22)errors.push("step title missing/too long (max 22)");
   if(typeof step.summary!=="string"||step.summary.length>57)errors.push("step summary max 57");
   if(step.action){if(typeof step.action.label!=="string"||step.action.label.length>23||!step.action.label.trim())errors.push("action label missing/too long");if(typeof step.action.url!=="string"||!/^https:\/\/[^/\s]+/.test(step.action.url))errors.push("action URL must be https")}
  }
  if(lane.edges!==undefined&&!Array.isArray(lane.edges))errors.push("edges must be an array");
  for(const edge of Array.isArray(lane.edges)?lane.edges:[]){
   if(!seen.has(edge.from)||!seen.has(edge.to)||edge.from===edge.to)errors.push("edge endpoints invalid");
   if(!["sequence","conditional"].includes(edge.kind))errors.push("edge type invalid");
   if(lane.steps.findIndex(s=>s.id===edge.to)!==lane.steps.findIndex(s=>s.id===edge.from)+1)errors.push("edges must connect adjacent steps; do not invent flow");
  }
 }
 return errors;
}

export function compileFlow(graph,profile){
 const issues=checkGraph(graph,profile);if(issues.length)throw Error(issues.join("; "));
 const xs=[24,199,374,549],objects=[],colors=profile.colors,add=(type,id,box,props={})=>objects.push({id,type,box,...props});
 add("header",graph.id+"_hdr",{x:24,y:12,w:672,h:67},{eyebrow:graph.eyebrow,title:graph.title,qualifier:graph.qualifier,colors});
 graph.lanes.forEach((lane,li)=>{
  const y=li===0?116:267,h=li===0?102:89;
  add("lane_label",graph.id+`_l${li}_label`,{x:24,y:li===0?90:241,w:672,h:19},{text:`0${li+1} / ${lane.title}`,color:li===0?colors.action:colors.secondary});
  const idx=new Map();
  lane.steps.forEach((step,si)=>{
   idx.set(step.id,si);
   const accent=step.kind==="gate"||step.proof_state==="unverified"?colors.gate:step.proof_state==="verified"?colors.verified:li===0?colors.action:colors.secondary;
   add("card",graph.id+`_l${li}_s${si}`,{x:xs[si],y,w:144,h},{step,accent,ink:colors.ink,muted:colors.muted,panel:colors.panel});
  });
  for(const edge of lane.edges||[]){
   const si=idx.get(edge.from);
   add("arrow",graph.id+`_l${li}_e${si}`,{x:xs[si]+145,y:y+(h-25)/2,w:29,h:25},{accent:edge.kind==="conditional"?colors.gate:li===0?colors.action:colors.secondary,kind:edge.kind});
  }
 });
 if(graph.footer){if(graph.footer.length>103)throw Error("footer max 103 chars");add("footer",graph.id+"_footer",{x:24,y:375,w:672,h:24},{text:graph.footer,accent:colors.gate})}
 return {schema:"slide-flow-ir/v1",style_id:profile.id,style_version:profile.version,graph_id:graph.id,page:{width_pt:720,height_pt:405},objects,proof_ceiling:"COMPILED_GEOMETRY_ONLY"};
}

export function auditIR(ir){
 const errors=[],cards=ir.objects.filter(o=>o.type==="card"),arrows=ir.objects.filter(o=>o.type==="arrow");
 for(const o of ir.objects){let b=o.box;if(b.x<0||b.y<0||b.x+b.w>ir.page.width_pt||b.y+b.h>ir.page.height_pt)errors.push("out of bounds: "+o.id)}
 for(const a of arrows)if(cards.some(c=>a.box.y<c.box.y+c.box.h&&a.box.y+a.box.h>c.box.y&&a.box.x<c.box.x+c.box.w&&a.box.x+a.box.w>c.box.x))errors.push("arrow overlaps card: "+a.id);
 if(new Set(ir.objects.map(x=>x.id)).size!==ir.objects.length)errors.push("duplicate element id");
 return errors;
}
