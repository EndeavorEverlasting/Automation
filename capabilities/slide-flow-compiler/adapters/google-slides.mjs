/** Emits native editable Google Slides shapes, connectors and hyperlink text. No API calls. */

import { auditIR } from '../compile.mjs';

export function hexColor(hex){return {red:parseInt(hex.slice(1,3),16)/255,green:parseInt(hex.slice(3,5),16)/255,blue:parseInt(hex.slice(5,7),16)/255};}

export function toGoogleSlidesRequests(ir,slideId){
 if(auditIR(ir).length)throw Error(auditIR(ir).join('; '));
 if(ir?.schema!=="slide-flow-ir/v1")throw Error("validated slide-flow IR required");
 if(typeof slideId!=="string"||!/^[-A-Za-z0-9_:]{5,50}$/.test(slideId))throw Error("existing slide objectId required");
 const requests=[],color=hexColor,sz=(w,h)=>({width:{magnitude:w,unit:"PT"},height:{magnitude:h,unit:"PT"}}),tr=(x,y)=>({scaleX:1,scaleY:1,translateX:x,translateY:y,unit:"PT"});
 const shape=(id,type,b,fill=null,outline=null,alpha=1)=>{
  requests.push({createShape:{objectId:id,shapeType:type,elementProperties:{pageObjectId:slideId,size:sz(b.w,b.h),transform:tr(b.x,b.y)}}});
  requests.push({updateShapeProperties:{objectId:id,shapeProperties:{shapeBackgroundFill:fill?{solidFill:{color:{rgbColor:color(fill)},alpha}}:{propertyState:"NOT_RENDERED"},outline:outline?{outlineFill:{solidFill:{color:{rgbColor:color(outline)}}},weight:{magnitude:1.2,unit:"PT"},propertyState:"RENDERED"}:{propertyState:"NOT_RENDERED"}},fields:"shapeBackgroundFill,outline"}});
 };
 const text=(id,label,b,pt,ink,bold=false,url=null)=>{
  shape(id,"TEXT_BOX",b);
  requests.push({insertText:{objectId:id,insertionIndex:0,text:label}});
  let style={fontFamily:"Arial",fontSize:{magnitude:pt,unit:"PT"},foregroundColor:{opaqueColor:{rgbColor:color(ink)}},bold};
  if(url)style.link={url};
  requests.push({updateTextStyle:{objectId:id,textRange:{type:"ALL"},style,fields:Object.keys(style).join(",")}});
 };
 for(const ob of ir.objects){
  const b=ob.box;
  if(ob.type==="header"){
   shape(ob.id+"_band","RECTANGLE",{x:0,y:0,w:720,h:81},ob.colors.canvas,null,.93);
   shape(ob.id+"_rail","RECTANGLE",{x:20,y:21,w:5,h:45},ob.colors.action);
   text(ob.id+"_eye",ob.eyebrow,{x:39,y:11,w:645,h:19},10.2,ob.colors.action,true);
   text(ob.id+"_title",ob.title,{x:39,y:32,w:655,h:36},26,ob.colors.ink,true);
   text(ob.id+"_sub",ob.qualifier,{x:39,y:68,w:662,h:15},9.6,ob.colors.muted,true);
  }else if(ob.type==="lane_label"){
   text(ob.id,ob.text,b,10.9,ob.color,true);
  }else if(ob.type==="card"){
   const s=ob.step;shape(ob.id+"_panel","ROUND_RECTANGLE",b,ob.panel,ob.accent,.94);
   shape(ob.id+"_rail","RECTANGLE",{x:b.x+2,y:b.y+11,w:4,h:b.h-22},ob.accent);
   text(ob.id+"_head",s.title,{x:b.x+11,y:b.y+12,w:b.w-21,h:27},15.1,ob.ink,true);
   const shortCard=b.h<98;
   text(ob.id+"_description",s.summary,{x:b.x+11,y:b.y+44,w:b.w-21,h:shortCard?20:30},9.5,ob.muted);
   if(s.action)text(ob.id+"_action",s.action.label,{x:b.x+11,y:b.y+b.h-24,w:b.w-20,h:14},9.3,ob.accent,true,s.action.url);
  }else if(ob.type==="arrow"){
   shape(ob.id,"RIGHT_ARROW",b,ob.accent);
  }else if(ob.type==="footer"){
   shape(ob.id+"_bar","ROUND_RECTANGLE",b,ob.canvas,ob.accent,.96);
   text(ob.id+"_text",ob.text,{x:b.x+11,y:b.y+5,w:b.w-21,h:17},9.4,ob.accent,true);
  }else throw Error("unsupported IR object type: "+ob.type);
 }
 return {schema:"google-slides-batch-update-plan/v1",slide_id:slideId,requests,proof_ceiling:"REQUESTS_COMPILED_NOT_PUBLISHED"};
}
