'use client';
import {FormEvent,useEffect,useState} from 'react';
import Link from 'next/link';
import {api} from '../lib/api';
type Evidence={id:string,evidence_id:string,original_filename:string,mime_type:string,file_size:number};
type Source={source_id:string,evidence_id:string,label:string,filename:string,sha256:string,excerpt:string,limited:boolean,page:number|null,method:string,uncertain:boolean};
type Result={warnings:string[],answered:boolean,model:string,notice:string,sources:Source[],claims:{text:string,citations:{source_id:string,quote:string}[]}[]};
export default function CaseAssistant(){
 const [cases,setCases]=useState<{id:string,case_number:string,title:string}[]>([]);
 const [caseId,setCaseId]=useState('');const [files,setFiles]=useState<Evidence[]>([]);
 const [selected,setSelected]=useState<string[]>([]);const [question,setQuestion]=useState('');
 const [forceOcr,setForceOcr]=useState(false);const [mode,setMode]=useState('question');const [consent,setConsent]=useState(false);
 const [status,setStatus]=useState<{enabled:boolean,message:string,model:string}|null>(null);
 const [busy,setBusy]=useState(false);const [loading,setLoading]=useState(false);
 const [error,setError]=useState('');const [result,setResult]=useState<Result|null>(null);
 useEffect(()=>{let live=true;Promise.all([api('/assistant/status'),api('/cases')]).then(([s,c])=>{if(live){setStatus(s);setCases(c)}}).catch(e=>{if(live)setError(e.message)});return()=>{live=false}},[]);
 useEffect(()=>{let live=true;setFiles([]);setSelected([]);setResult(null);setConsent(false);setError('');
 if(caseId){setLoading(true);api('/evidence?case_id='+encodeURIComponent(caseId)).then(e=>{if(live)setFiles(e)}).catch(e=>{if(live)setError(e.message)}).finally(()=>{if(live)setLoading(false)})}else setLoading(false);
 return()=>{live=false}},[caseId]);
 const supported=(e:Evidence)=>['text/plain','application/pdf','image/png','image/jpeg'].includes(e.mime_type)&&e.file_size<=10485760;
 async function submit(event:FormEvent){event.preventDefault();setBusy(true);setError('');setResult(null);
 try{setResult(await api('/assistant/ask',{method:'POST',body:JSON.stringify({case_id:caseId,evidence_ids:selected,question,mode,force_ocr:forceOcr,confirm_demo_external_processing:consent})}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <><div className="page-heading"><div><span className="eyebrow">EVIDENCE ASSISTANCE</span><h1>Case assistant</h1><p>Ask about selected evidence or generate a summary with source quotations.</p></div></div>
 <div className="notice">Google Gemini processes the question and selected decrypted text outside this computer. Use fictional demo evidence only: Google’s unpaid service may use submissions to improve its products. Original encrypted files and custody records remain unchanged.</div>
 {error&&<div className="notice error" role="alert">{error}</div>}
 {status&&!status.enabled&&<div className="notice">{status.message}. See <code>docs/AI_ASSISTANT.md</code>. Core evidence features remain available.</div>}
 <form className="panel form-panel" onSubmit={submit}><fieldset disabled={busy} style={{border:0,padding:0,minWidth:0}}>
 <label className="field"><span>Case</span><select required value={caseId} onChange={e=>setCaseId(e.target.value)}><option value="">Choose an authorized case</option>{cases.map(c=><option key={c.id} value={c.id}>{c.case_number} — {c.title}</option>)}</select></label>
 <p>Select up to four files, each at most 10 MiB. Text, PDFs (including scans), PNG and JPEG document photos are supported. Printed English OCR runs locally. Handwriting is not reliably supported. PDFs are limited to 20 pages. DOCX and video are not supported.</p>
 {loading?<p>Loading case evidence…</p>:files.map(e=><label className="checkbox" key={e.id} style={{display:'flex',marginBottom:12}}><input type="checkbox" checked={selected.includes(e.id)} disabled={!supported(e)||(!selected.includes(e.id)&&selected.length>=4)} onChange={event=>{setSelected(event.target.checked?[...selected,e.id]:selected.filter(id=>id!==e.id));setConsent(false);setResult(null)}}/><span>{e.evidence_id} · {e.original_filename}{!supported(e)&&' — unsupported format or too large'}</span></label>)}
 {caseId&&!loading&&!files.length&&<p>No evidence in this case.</p>}
 <label className="checkbox"><input type="checkbox" checked={forceOcr} onChange={e=>{setForceOcr(e.target.checked);setResult(null)}}/> Scan every PDF page (use for mixed typed text and scanned notes; slower)</label>
 <label className="field"><span>Task</span><select value={mode} onChange={e=>{setMode(e.target.value);setResult(null)}}><option value="question">Answer a question</option><option value="summary">Summarize selected excerpts</option></select></label>
 {mode==='question'&&<label className="field"><span>Question</span><textarea required maxLength={2000} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="What discrepancy is described in these records?"/></label>}
 <label className="checkbox"><input type="checkbox" required checked={consent} onChange={e=>setConsent(e.target.checked)}/> I confirm these are fictional demo files and authorize sending my question and selected text to Google.</label>
 <button className="button primary" style={{marginTop:16}} disabled={busy||loading||!status?.enabled||!caseId||!selected.length||!consent}>{busy?'Reading selected evidence…':mode==='summary'?'Generate summary':'Ask Gemini'}</button>
 </fieldset></form>
 {result&&<section className="panel" aria-live="polite"><h2>AI-derived assistance</h2><p className="subtle">{result.notice}</p><p>Model: {result.model}</p>{result.warnings?.map((warning,i)=><p className="notice" key={i}>{warning}</p>)}
 {!result.answered&&<p>The selected excerpts do not provide enough information to answer. Choose different evidence or narrow the question.</p>}
 {result.claims.map((claim,i)=><div key={i} style={{marginBottom:24}}><p style={{whiteSpace:'pre-wrap'}}>{claim.text}</p>{claim.citations.map((c,j)=>{const s=result.sources.find(s=>s.source_id===c.source_id);return <blockquote key={j} style={{borderLeft:'3px solid #58b8a8',paddingLeft:14,whiteSpace:'pre-wrap'}}>{c.quote}<br/>{s&&<Link href={'/evidence/'+s.evidence_id}>{s.label} · {s.filename}{s.page ? ` · Page ${s.page}` : ""}{s.method==='ocr'?' · OCR — check original':''}</Link>}</blockquote>})}</div>)}
 <h3>Excerpts supplied to Gemini</h3>{result.sources.map(s=><details key={s.source_id}><summary>{s.label} · {s.filename}{s.page ? ` · Page ${s.page}` : ""}{s.method==='ocr'?' · OCR':''}{s.uncertain?' · uncertain words':''}{s.limited?' — limited excerpt / PDF page coverage':''}</summary><p style={{overflowWrap:'anywhere'}}>Original SHA-256: {s.sha256}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{s.excerpt}</pre></details>)}
 </section>}</>
}
