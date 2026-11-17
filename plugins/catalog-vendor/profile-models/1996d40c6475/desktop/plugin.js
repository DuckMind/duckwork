/** Profile Models · a read-only, profile-scoped Duckwork Desktop status-bar plugin. */
import { host, haptic, icons, Popover, PopoverContent, PopoverTrigger, STATUSBAR_AREAS, useValue, useQuery } from '@duckwork/plugin-sdk'
import { useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'profile-models'
const EMPTY_VALUE = { get:()=>null,listen:()=>()=>{} }
const CSS = `
.pm-chip,.pm-panel{--pm-accent:#8b5cf6;--pm-cyan:#06b6d4;--pm-ink:color-mix(in srgb,var(--ui-text-primary) 65%,var(--pm-accent));--pm-cyan-ink:color-mix(in srgb,var(--ui-text-primary) 65%,var(--pm-cyan))}
.pm-chip{display:inline-flex;flex-shrink:0;align-items:center;gap:5px;height:25px;justify-content:center;margin:0 2px 2px;padding:0 7px 2px;border:1px solid var(--ui-stroke-secondary);border-radius:7px;background:color-mix(in srgb,var(--ui-accent) 5%,transparent);color:var(--ui-text-secondary);font-size:11px;cursor:pointer;white-space:nowrap;transition:background .15s,border-color .15s}
.pm-chip:hover,.pm-chip[data-state="open"]{background:color-mix(in srgb,var(--ui-accent) 13%,transparent);border-color:color-mix(in srgb,var(--ui-accent) 40%,var(--ui-stroke-secondary))}
.pm-chip-name{flex-shrink:0;white-space:nowrap;line-height:1}
.pm-chip{background:color-mix(in srgb,var(--pm-accent) 15%,transparent);border-color:color-mix(in srgb,var(--pm-accent) 38%,var(--ui-stroke-secondary));color:var(--pm-ink)}
.pm-chip:hover,.pm-chip[data-state="open"]{background:color-mix(in srgb,var(--pm-accent) 24%,transparent);border-color:var(--pm-accent)}
.pm-icon{color:var(--pm-ink);flex-shrink:0}
.pm-panel{width:360px;max-width:calc(100vw - 24px);max-height:min(560px,calc(100vh - 70px));display:flex;flex-direction:column;color:var(--ui-text-primary);font-size:12px;line-height:1.45}
.pm-panel .pm-icon{color:var(--pm-ink)}
.pm-head{padding:12px 14px 9px;display:flex;align-items:center;gap:10px}
.pm-mark{display:grid;place-items:center;width:24px;height:24px;border-radius:7px;background:color-mix(in srgb,var(--pm-accent) 16%,transparent)}
.pm-title{font-size:14px;font-weight:600;letter-spacing:-.02em}
.pm-profile{font-size:10px;color:var(--ui-text-tertiary);max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pm-refresh{margin-left:auto;display:inline-flex;align-items:center;gap:5px;border-radius:5px;padding:5px 7px;color:var(--ui-text-tertiary);font-size:10px;cursor:pointer;flex-shrink:0}
.pm-refresh:hover{background:var(--chrome-action-hover);color:var(--ui-text-primary)}
.pm-refresh:disabled{opacity:.5;cursor:default}
.pm-chip:focus-visible{outline:2px solid var(--ui-accent);outline-offset:2px}
.pm-refresh:focus-visible,.pm-tabs button:focus-visible,.pm-chain summary:focus-visible{outline:2px solid var(--pm-accent);outline-offset:2px}
.pm-hero{margin:0 12px 9px;padding:8px 9px;border:1px solid color-mix(in srgb,var(--pm-accent) 30%,var(--ui-stroke-secondary));border-radius:8px;background:linear-gradient(115deg,color-mix(in srgb,var(--pm-accent) 13%,transparent),color-mix(in srgb,var(--pm-cyan) 5%,transparent))}
.pm-hero .pm-eyebrow,.pm-tally strong{color:var(--pm-ink)}
.pm-eyebrow{font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--ui-text-tertiary);margin-bottom:5px}
.pm-main-name{font-size:14px;line-height:1.4;font-weight:600;letter-spacing:-.02em;overflow-wrap:anywhere}
.pm-meta{font-size:10px;color:var(--ui-text-tertiary);margin-top:3px;overflow-wrap:anywhere}
.pm-tally{display:flex;gap:12px;margin-top:8px;padding-top:7px;border-top:1px solid var(--ui-stroke-secondary);font-size:10px;color:var(--ui-text-tertiary)}
.pm-tally strong{color:var(--ui-text-secondary);font-weight:600;font-variant-numeric:tabular-nums;margin-right:3px}
.pm-controls{padding:0 12px 9px;display:flex;align-items:center;gap:9px}
.pm-search{flex:1;min-width:0;display:flex;align-items:center;gap:6px;border:1px solid var(--ui-stroke-secondary);border-radius:6px;padding:5px 7px;color:var(--ui-text-quaternary)}
.pm-search:focus-within{border-color:var(--pm-accent)}
.pm-search input{min-width:0;width:100%;outline:none;background:transparent;color:var(--ui-text-primary);font-size:11px}
.pm-tabs{display:flex;gap:2px;border:1px solid var(--ui-stroke-secondary);padding:2px;border-radius:6px;flex-shrink:0}
.pm-tabs button{border-radius:4px;padding:4px 7px;font-size:10px;color:var(--ui-text-tertiary);cursor:pointer}
.pm-tabs button[aria-pressed="true"]{background:color-mix(in srgb,var(--pm-accent) 18%,transparent);color:var(--pm-ink)}
.pm-body{min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:0 12px 12px}
.pm-section+.pm-section{margin-top:14px}
.pm-sec-head{display:flex;align-items:center;gap:6px;padding:4px 4px 8px;font-size:10px;font-weight:550;color:var(--ui-text-tertiary)}
.pm-sec-head span:last-child{margin-left:auto;font-size:9px;color:var(--ui-text-quaternary);font-variant-numeric:tabular-nums}
.pm-card{min-width:0;padding:8px 9px;border:1px solid var(--ui-stroke-secondary);border-radius:6px}
.pm-card+.pm-card{margin-top:6px}
.pm-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;align-items:start}
.pm-grid>.pm-card+.pm-card{margin-top:0}
.pm-section[data-group="aux"] .pm-sec-head{color:var(--pm-cyan-ink)}
.pm-section[data-group="aux"] .pm-card{border-left:2px solid var(--pm-cyan);background:color-mix(in srgb,var(--pm-cyan) 4%,transparent)}
.pm-section[data-group="sub"] .pm-sec-head{color:var(--pm-ink)}
.pm-section[data-group="sub"] .pm-card{border-left:2px solid var(--pm-accent);background:color-mix(in srgb,var(--pm-accent) 4%,transparent)}
.pm-card[data-disabled="true"]{opacity:.65}
.pm-role{display:flex;flex-wrap:wrap;align-items:center;gap:4px;font-size:10px;color:var(--ui-text-tertiary);margin-bottom:3px}
.pm-name{font-size:12px;font-weight:550;color:var(--ui-text-primary);overflow-wrap:anywhere;line-height:1.4}
.pm-tag{font-size:9px;padding:1px 5px;border:1px solid var(--ui-stroke-secondary);border-radius:4px;color:var(--ui-text-quaternary);white-space:nowrap}
.pm-tag{background:color-mix(in srgb,var(--pm-accent) 10%,transparent);border-color:color-mix(in srgb,var(--pm-accent) 24%,var(--ui-stroke-secondary));color:var(--pm-ink)}
.pm-card[data-disabled="true"] .pm-tag{background:color-mix(in srgb,#f59e0b 13%,transparent);border-color:color-mix(in srgb,#f59e0b 35%,var(--ui-stroke-secondary));color:color-mix(in srgb,var(--ui-text-primary) 65%,#f59e0b)}
.pm-chain{margin-top:8px;border-top:1px solid var(--ui-stroke-secondary);padding-top:7px}
.pm-chain summary{font-size:10px;color:var(--ui-text-tertiary);cursor:pointer;width:fit-content}
.pm-chain ol{list-style:none;padding:1px 0 0;margin:0;counter-reset:pm-fallback}
.pm-chain li{position:relative;padding:7px 0 0 20px;counter-increment:pm-fallback}
.pm-chain li:before{content:counter(pm-fallback);position:absolute;left:0;top:9px;font-size:9px;color:var(--ui-text-quaternary);font-variant-numeric:tabular-nums}
.pm-chain li .pm-name{font-size:11px;font-weight:450}
.pm-role-tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.pm-role-tags span{font-size:9px;padding:2px 5px;border:1px solid var(--ui-stroke-secondary);border-radius:4px;color:var(--ui-text-tertiary)}
.pm-role-tags span{background:color-mix(in srgb,var(--pm-accent) 9%,transparent);border-color:color-mix(in srgb,var(--pm-accent) 22%,var(--ui-stroke-secondary));color:var(--pm-ink)}
.pm-state{padding:20px 5px;color:var(--ui-text-tertiary);font-size:11px}
.pm-foot{padding:10px 17px;border-top:1px solid var(--ui-stroke-secondary);font-size:10px;color:var(--ui-text-quaternary)}
@media(prefers-reduced-motion:reduce){.pm-chip{transition:none}}
@media(max-width:360px){.pm-grid{grid-template-columns:1fr}}
`

function prettyRole(key) {
  const special = { moa_reference:'MoA reference',moa_aggregator:'MoA aggregator',subagent:'Sub-agent' }
  return special[key] || String(key).replace(/_/g,' ').replace(/^./,s=>s.toUpperCase())
}
function entries(value) { return value && typeof value === 'object' && !Array.isArray(value) ? value : {} }
function modelSlot(value, parent) {
  const slot = typeof value === 'string' ? { model:value } : entries(value)
  const model = typeof slot.model === 'string' && slot.model.trim() ? slot.model.trim() : parent?.model || ''
  const configuredProvider = typeof slot.provider === 'string' ? slot.provider.trim() : ''
  // Duckwork's auto provider follows the parent route.
  const provider = configuredProvider && !['auto','default'].includes(configuredProvider) ? configuredProvider : parent?.provider || ''
  return { model,provider,inherited:!slot.model,enabled:slot.enabled !== false }
}
function chain(value,parent) {
  return (Array.isArray(value) ? value : []).map(item=>modelSlot(item,parent)).filter(item=>item.model)
}

/** Keep only model routing fields. Never retain the full config or credentials. */
function parseConfig(config) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) throw new Error('Invalid profile config')
  const configModel = typeof config.model === 'string' ? { default:config.model } : entries(config.model)
  const main = modelSlot({ model:configModel.default || configModel.model,provider:configModel.provider })
  const routes = []
  if (main.model) routes.push({ ...main,key:'main',role:'Main',group:'main',fallbacks:chain(config.fallback_providers,main) })
  const auxiliary = entries(config.auxiliary)
  for (const [key,value] of Object.entries(auxiliary)) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) continue
    const slot = modelSlot(value,main)
    if (!slot.model) continue
    routes.push({ ...slot,key:'aux:'+key,role:prettyRole(key),group:key.startsWith('moa_')?'sub':'aux',fallbacks:chain(value.fallback_chain,slot) })
  }
  const worker = entries(config.delegation?.model ? config.delegation : config.subagent?.model ? config.subagent : config.delegation || config.subagent)
  // An omitted worker model inherits the parent's model; legacy pins remain supported.
  const workerSlot = modelSlot(worker,main)
  if (workerSlot.model) routes.push({ ...workerSlot,key:'worker',role:'Sub-agent',group:'sub',
    fallbacks:chain(worker.fallback_providers ?? worker.fallback_chain ?? config.fallback_providers,workerSlot) })
  const moa = entries(config.moa)
  for (const [name,value] of Object.entries(entries(moa.presets))) {
    const preset = entries(value)
    const add = (slot,key,role) => {
      const parsed = modelSlot(slot)
      if (parsed.model) routes.push({ ...parsed,key,role,group:'sub',preset:name,
        defaultPreset:name===moa.default_preset,enabled:parsed.enabled && preset.enabled!==false && moa.enabled!==false,
        fallbacks:chain(entries(slot).fallback_chain,parsed) })
    }
    if (Array.isArray(preset.reference_models)) preset.reference_models.forEach((slot,i)=>add(slot,`moa:${name}:ref:${i}`,`${prettyRole(name)} · reference ${i+1}`))
    if (preset.aggregator) add(preset.aggregator,`moa:${name}:agg`,`${prettyRole(name)} · aggregator`)
  }
  return { main,routes }
}

function groupModels(data) {
  const grouped = new Map()
  const add = (slot,role,enabled) => {
    const key = JSON.stringify([slot.provider,slot.model])
    if (!grouped.has(key)) grouped.set(key,{...slot,key,roles:[]})
    const label = role + (enabled===false ? ' · disabled' : '')
    if (!grouped.get(key).roles.includes(label)) grouped.get(key).roles.push(label)
  }
  for (const route of data.routes) {
    add(route,route.role,route.enabled)
    route.fallbacks.forEach((slot,i)=>add(slot,`${route.role} · fallback ${i+1}`,route.enabled && slot.enabled))
  }
  return [...grouped.values()]
}
function matches(slot,text) {
  return [slot.model,slot.provider,slot.role,...(slot.roles || [])].join(' ').toLowerCase().includes(text)
}
async function fetchModels(scope) {
  const params = { key:'full',profile:scope.profile }
  // Never retry without a profile: that would silently substitute the launch config.
  let payload
  if (typeof host.requestProfile === 'function') {
    const route = scope.connectionId ? { connectionId:scope.connectionId,profile:scope.profile,targetProfile:scope.profile,mode:scope.connectionId==='local'?'local':'remote' } : scope.profile
    payload = await host.requestProfile(route,'config.get',params,15000)
  } else {
    payload = await host.request('config.get',params)
  }
  return parseConfig(payload?.config || payload)
}

function ModelName({ slot,main=false }) {
  return jsxs('div',{children:[
    jsx('div',{className:main?'pm-main-name':'pm-name',title:slot.model,children:slot.model || 'Not configured'}),
    jsx('div',{className:'pm-meta',children:slot.provider || 'Auto provider'})
  ]})
}
function Fallbacks({ items }) {
  if (!items.length) return null
  return jsxs('details',{className:'pm-chain',children:[
    jsx('summary',{children:`${items.length} fallback${items.length===1?'':'s'} · in order`}),
    jsx('ol',{children:items.map((slot,i)=>jsx('li',{children:jsxs('div',{children:[jsx(ModelName,{slot}),slot.enabled===false?jsx('span',{className:'pm-tag',children:'Disabled'}):null]})},i))})
  ]})
}
function RouteCard({ route }) {
  return jsxs('div',{className:'pm-card','data-disabled':!route.enabled,children:[
    jsxs('div',{className:'pm-role',children:[route.role,
      route.inherited?jsx('span',{className:'pm-tag',children:'Inherits main'}):null,
      !route.enabled?jsx('span',{className:'pm-tag',children:'Disabled'}):null,
      route.defaultPreset?jsx('span',{className:'pm-tag',children:'Default preset'}):null]}),
    jsx(ModelName,{slot:route}),jsx(Fallbacks,{items:route.fallbacks})
  ]})
}
function ModelsChip() {
  const [open,setOpen] = useState(false)
  const [view,setView] = useState('roles')
  const [search,setSearch] = useState('')
  const owner = useValue(host.state.focusedSessionOwner || host.state.focusedSessionProfile || EMPTY_VALUE)
  const gatewayProfile = useValue(host.state.profile)
  const activeConnection = useValue(host.state.connectionId)
  const gateway = useValue(host.state.gateway)
  const profile = (typeof owner==='object' ? owner?.profile : owner) || gatewayProfile || 'default'
  const connectionId = (typeof owner==='object' ? owner?.connectionId : null) || activeConnection
  const query = useQuery({ queryKey:[ID,'config',connectionId,profile,gateway],
    queryFn:()=>fetchModels({connectionId,profile}),staleTime:30000,retry:1,
    refetchInterval:open?60000:false,refetchIntervalInBackground:false })
  const data = query.data
  const models = data ? groupModels(data) : []
  const text = search.trim().toLowerCase()
  const mainModel = models.find(slot=>slot.model===data?.main.model && slot.provider===data?.main.provider)
  const filteredModels = models.filter(slot=>slot!==mainModel && matches(slot,text))
  const routes = data?.routes || []
  const fallbacks = routes.reduce((n,r)=>n+r.fallbacks.length,0)
  function changeOpen(value) {
    haptic('tap');setOpen(value)
    if (value) { setSearch('');query.refetch() }
  }
  return jsxs(Popover,{open,onOpenChange:changeOpen,children:[
    jsx(PopoverTrigger,{asChild:true,children:jsxs('button',{type:'button',className:'pm-chip',
      'aria-label':`Show models configured for ${profile}${data ? ' · '+data.main.model+' · '+models.length+' models' : ''}`,
      title:`${profile} · configured main: ${data?.main.model || 'unavailable'} · ${models.length} distinct model routes`,
      children:[jsx(icons.Cpu,{size:12,className:'pm-icon'}),
        jsx('span',{className:'pm-chip-name',children:data ? data.main.model || 'No main model' : query.isError?'Models unavailable':'Loading models…'})]})}),
    jsx(PopoverContent,{side:'top',align:'end',className:'w-auto p-0',style:{padding:0,width:'auto',borderRadius:14,overflow:'hidden'},
      'aria-label':`Models configured for ${profile}`,children:jsxs('div',{className:'pm-panel',children:[
      jsxs('div',{className:'pm-head',children:[jsx('div',{className:'pm-mark',children:jsx(icons.Cpu,{size:17,className:'pm-icon'})}),
        jsxs('div',{children:[jsx('div',{className:'pm-title',children:'Profile models'}),jsx('div',{className:'pm-profile',title:profile,children:profile})]}),
        jsxs('button',{type:'button',className:'pm-refresh',disabled:query.isFetching,onClick:()=>query.refetch(),
          children:[jsx(icons.RefreshCw,{size:11}),query.isFetching?'Updating…':'Refresh']})]}),
      data ? jsxs('div',{className:'pm-hero',children:[jsx('div',{className:'pm-eyebrow',children:'Profile default'}),
        data.main.model ? jsx(ModelName,{slot:data.main,main:true}) : jsx('div',{className:'pm-name',children:'Main model not configured'}),
        view==='models' && mainModel ? jsx('div',{className:'pm-role-tags',children:mainModel.roles.filter(role=>role!=='Main').map(role=>jsx('span',{children:role},role))}) : null,
        jsx(Fallbacks,{items:routes.find(r=>r.key==='main')?.fallbacks || []}),
        jsxs('div',{className:'pm-tally',children:[jsxs('span',{children:[jsx('strong',{children:models.length}),'models']}),
          jsxs('span',{children:[jsx('strong',{children:routes.length}),'roles']}),jsxs('span',{children:[jsx('strong',{children:fallbacks}),'fallbacks']})]})]}) : null,
      data ? jsxs('div',{className:'pm-controls',children:[jsxs('label',{className:'pm-search',children:[jsx(icons.Search,{size:12,'aria-hidden':true}),
        jsx('input',{type:'search',value:search,'aria-label':'Filter models, roles or providers',placeholder:'Find a model or role…',onChange:e=>setSearch(e.target.value)})]}),
        jsx('div',{className:'pm-tabs',children:['roles','models'].map(kind=>jsx('button',{type:'button','aria-pressed':view===kind,onClick:()=>setView(kind),children:kind==='roles'?'By role':'By model'},kind))})]}) : null,
      jsx('div',{className:'pm-body',children:!data ? jsx('div',{className:'pm-state',role:'status',children:query.isError?'Could not read this profile. Refresh to try again.':'Reading profile models…'}) : view==='models' ?
        filteredModels.length ? filteredModels.map(slot=>jsxs('div',{className:'pm-card',children:[jsx(ModelName,{slot}),
          jsx('div',{className:'pm-role-tags',children:slot.roles.map(role=>jsx('span',{children:role},role))})]},slot.key)) : text && !(mainModel && matches(mainModel,text)) ? jsx('div',{className:'pm-state',children:'No matching models.'}) : null :
        (()=>{
          const sections=[['aux','Auxiliary tasks',icons.Layers3],['sub','Sub-agent & MoA',icons.Users]]
          const selected = routes.filter(r=>r.group!=='main' && (matches(r,text)||r.fallbacks.some(slot=>matches(slot,text))))
          const mainRoute = routes.find(r=>r.key==='main')
          if (!selected.length) return !routes.length || (text && !(mainRoute && (matches(mainRoute,text)||mainRoute.fallbacks.some(slot=>matches(slot,text))))) ? jsx('div',{className:'pm-state',children:routes.length?'No matching roles.':'No models configured.'}) : null
          return sections.map(([group,label,icon])=>{
            const rows=selected.filter(r=>r.group===group)
            if (!rows.length) return null
            return jsxs('div',{className:'pm-section','data-group':group,children:[jsxs('div',{className:'pm-sec-head',children:[jsx(icon,{size:12}),label,jsx('span',{children:rows.length})]}),
              jsx('div',{className:group==='aux'?'pm-grid':'pm-stack',children:rows.map(route=>jsx(RouteCard,{route},route.key))})]},group)
          })
        })()}),
      jsx('div',{className:'pm-foot',role:'status',children:query.isError && data ? 'Refresh failed · showing this profile’s last saved view.' : 'Profile configuration · chat overrides can differ.'})
    ]})})
  ]})
}
export default {
  id:ID,name:'Profile Models',description:'Profile model map with role and model views, ordered fallbacks and search.',defaultEnabled:true,
  register(ctx) {
    const style=document.createElement('style');style.textContent=CSS;document.head.append(style)
    ctx.onDispose(()=>style.remove())
    ctx.register({id:'chip',area:STATUSBAR_AREAS.right,order:140,render:()=>jsx(ModelsChip,{})})
  }
}
