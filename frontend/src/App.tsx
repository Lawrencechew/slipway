import React, {useState} from 'react'

function Login({onSetToken}:{onSetToken:(t:string)=>void}){
  const [name, setName] = useState('alice')
  async function create(){
    const r = await fetch('/users', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({username:name})})
    const j = await r.json()
    localStorage.setItem('api_key', j.api_key)
    onSetToken(j.api_key)
  }
  return (<div>
    <h3>Sign in</h3>
    <input value={name} onChange={e=>setName(e.target.value)} />
    <button onClick={create}>Create API Key</button>
  </div>)
}

export default function App(){
  const [token, setToken] = useState<string | null>(localStorage.getItem('api_key'))
  const [view, setView] = useState<'dash'|'create'|'plan'|'audit'>('dash')
  const [specBody, setSpecBody] = useState('')
  const [plan, setPlan] = useState<any>(null)

  if(!token) return <Login onSetToken={(t)=>{setToken(t); setView('dash')}} />

  async function createSpec(){
    const spec = JSON.parse(specBody)
    const r = await fetch('/specs', {method:'POST', headers:{'content-type':'application/json','authorization':`Bearer ${token}`}, body: JSON.stringify(spec)})
    const j = await r.json()
    alert('Spec created: '+j.fingerprint)
  }

  async function genPlan(){
    const spec = JSON.parse(specBody)
    const r = await fetch('/plans', {method:'POST', headers:{'content-type':'application/json','authorization':`Bearer ${token}`}, body: JSON.stringify(spec)})
    const j = await r.json()
    setPlan(j)
    setView('plan')
  }

  async function approve(){
    if(!plan) return
    const r = await fetch(`/plans/${plan.id}/approve`, {method:'POST', headers:{'authorization':`Bearer ${token}`}})
    const j = await r.json()
    alert('Approved')
  }

  return (
    <div style={{fontFamily:'Inter, system-ui', padding:20}}>
      <h1>PavedPath (Demo)</h1>
      <div style={{marginBottom:10}}>
        <button onClick={()=>setView('dash')}>Dashboard</button>
        <button onClick={()=>setView('create')}>Create Service</button>
        <button onClick={()=>setView('audit')}>Audit</button>
      </div>
      {view === 'dash' && (<div>
        <h2>Dashboard</h2>
        <p>Use Create Service to submit a ServiceSpec JSON.</p>
      </div>)}

      {view === 'create' && (<div>
        <h2>Create Service</h2>
        <textarea style={{width:'100%',height:240}} value={specBody} onChange={e=>setSpecBody(e.target.value)} placeholder='Paste ServiceSpec JSON here'></textarea>
        <div style={{marginTop:8}}>
          <button onClick={createSpec}>Save Spec</button>
          <button onClick={genPlan}>Generate Plan</button>
        </div>
      </div>)}

      {view === 'plan' && plan && (<div>
        <h2>Plan: {plan.id}</h2>
        <p>Status: {plan.status}</p>
        <h3>Artifacts</h3>
        <ul>
          {plan.artifacts.map((a:any,i:number)=>(<li key={i}>{a.path} — {a.reason}</li>))}
        </ul>
        <button onClick={approve}>Approve</button>
      </div>)}

      {view === 'audit' && (<div>
        <h2>Audit</h2>
        <p>Use the API to view audit history (not yet implemented in UI)</p>
      </div>)}
    </div>
  )
}
