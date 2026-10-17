'use strict';
const $=id=>document.getElementById(id);
let selected=null, sequence=0, uploading=false;
function message(text,error=false){$('message').textContent=text;$('message').classList.toggle('error',error);}
async function api(url,options={}){
  const response=await fetch(url,options);let value;
  try{value=await response.json();}catch{throw Error('The server returned an unreadable response.');}
  if(!response.ok)throw Error(typeof value.error==='string'?value.error:typeof value.detail==='string'?value.detail:'Request failed. Check your file or input.');
  return value;
}
function options(select,values,initial){const old=select.value;select.replaceChildren();for(const [value,label] of [['',initial],...values.map(v=>[v,v])]){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}select.value=values.includes(old)?old:'';}
async function status(){const s=await api('/api/status');$('modelState').textContent=s.semantic_available?'● Semantic model ready':'◌ Keyword-only mode';$('modelState').classList.toggle('offline',!s.semantic_available);$('modelState').title=s.message;options($('category'),s.categories,'All categories');options($('collection'),s.collections.map(c=>c.name),'All collections');$('collectionNames').replaceChildren();for(const c of s.collections){const o=document.createElement('option');o.value=c.name;$('collectionNames').append(o);}return s;}
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
async function load(){
  const token=++sequence;
  const params=new URLSearchParams({q:$('query').value,mode:$('mode').value,category:$('category').value,collection:$('collection').value,trash:$('trash').checked});
  try{
    $('searchNote').textContent='Searching locally…';const r=await api('/api/documents?'+params);
    if(token!==sequence)return;
    $('documents').replaceChildren();$('count').textContent=r.results.length;$('empty').hidden=r.results.length>0;
    $('searchNote').textContent=r.notice||`Mode: ${r.mode_used}. Scores are relevance signals, not probabilities.`;
    for(const doc of r.results){
      const card=node('button',undefined,'card');card.type='button';card.setAttribute('aria-label','Open '+doc.title);
      const top=node('div',undefined,'card-top');top.append(node('span',doc.filename.split('.').pop().toUpperCase(),'file-icon'),node('span',doc.category,'tag'));
      const foot=node('div',undefined,'card-foot');foot.append(node('span',doc.collection||'Uncollected'));
      if(doc.score!==undefined)foot.append(node('span',`Relevance ${doc.score.toFixed(3)}`,'score'));else foot.append(node('span',new Date(doc.created).toLocaleDateString()));
      card.append(top,node('h3',doc.title),node('div',doc.filename,'filename'),node('p',doc.excerpt||doc.summary,'card-summary'),foot);card.onclick=()=>openDocument(doc.id);$('documents').append(card);
    }
  }catch(error){if(token===sequence)message(error.message,true);}
}
async function upload(files){
  if(uploading)return;uploading=true;$('files').disabled=true;
  let successful=0;const errors=[];
  try{for(let i=0;i<files.length;i++){
    const file=files[i];message(`Processing ${i+1}/${files.length}: ${file.name}…`);
    if(file.size>8*1024*1024){errors.push(file.name+': exceeds 8 MiB');continue;}
    try{const form=new FormData();form.append('file',file);const r=await api('/api/upload',{method:'POST',body:form});successful++;if(r.duplicate)errors.push(file.name+': already in library'+(r.document.deleted?' (in Trash)':''));}catch(error){errors.push(file.name+': '+error.message);}
  }await status();await load();message(`${successful} file(s) processed.`+(errors.length?'\n'+errors.join('\n'):''),errors.length>0);
  }catch(error){message(error.message,true);}finally{uploading=false;$('files').disabled=false;$('files').value='';}
}
$('files').onchange=event=>upload(Array.from(event.target.files));
for(const type of ['dragenter','dragover'])$('dropzone').addEventListener(type,event=>{event.preventDefault();$('dropzone').classList.add('drag');});
for(const type of ['dragleave','drop'])$('dropzone').addEventListener(type,event=>{event.preventDefault();$('dropzone').classList.remove('drag');});
$('dropzone').addEventListener('drop',event=>upload(Array.from(event.dataTransfer.files)));
$('searchForm').onsubmit=event=>{event.preventDefault();load();};for(const id of ['category','collection','trash','mode'])$(id).onchange=load;
async function openDocument(id){
 try{const doc=await api('/api/documents/'+encodeURIComponent(id));selected=doc;
 $('detailTitle').textContent=doc.title;$('detailFilename').textContent=doc.filename;
 for(const [id,key] of [['editTitle','title'],['editCategory','category'],['editSummary','summary']])$(id).value=doc[key];
 $('editTags').value=doc.tags.join(', ');$('editCollection').value=doc.collection||'';
 $('extracted').textContent=doc.text;const s=doc.suggestions;
 $('suggestionInfo').textContent=`Suggested category: ${s.category} · Heuristic strength: ${s.classification_strength.toFixed(2)} (not probability). Evidence: ${s.classification_evidence.join(', ')||'no category terms'}. Suggested title: ${s.title}. Keywords: ${s.keywords.join(', ')}.`;
 $('suggestedSummary').textContent='Extractive summary: '+s.summary;$('warnings').textContent=doc.warnings.join(' ');
 $('download').href='/api/documents/'+encodeURIComponent(id)+'/original';$('trashDoc').textContent=doc.deleted?'Restore document':'Move to Trash';
 if(!$('detail').open)$('detail').showModal();
 }catch(error){message(error.message,true);}
}
$('closeDetail').onclick=()=>{$('detail').close();selected=null;};
$('editForm').onsubmit=async event=>{
 event.preventDefault();if(!selected)return;$('save').disabled=true;
 try{await api('/api/documents/'+encodeURIComponent(selected.id),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:$('editTitle').value,category:$('editCategory').value,summary:$('editSummary').value,tags:$('editTags').value.split(',').map(s=>s.trim()).filter(Boolean),collection:$('editCollection').value})});$('detail').close();selected=null;await status();await load();message('Metadata saved. Original automatic suggestions are preserved for comparison.');}
 catch(error){alert(error.message);}finally{$('save').disabled=false;}
};
$('trashDoc').onclick=async()=>{
 if(!selected)return;try{const id=selected.id;await api('/api/documents/'+encodeURIComponent(id)+(selected.deleted?'/restore':''),{method:selected.deleted?'POST':'DELETE'});const wasDeleted=selected.deleted;$('detail').close();selected=null;await status();await load();message(wasDeleted?'Document restored.':'Moved to Trash. Select Show Trash to restore it. Original files have not been erased.');}catch(error){alert(error.message);}
};
$('reindex').onclick=async()=>{if(!confirm('Rebuild missing embeddings for active documents? Existing vectors will be reused.'))return;$('reindex').disabled=true;message('Checking document embeddings…');try{const r=await api('/api/reindex',{method:'POST'});message(r.message);await load();}catch(error){message(error.message,true);}finally{$('reindex').disabled=false;}};
(async()=>{try{const s=await status();if(s.message)message(s.message);await load();}catch(error){message('Could not connect to the local server. '+error.message,true);}})();
