import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, ArrowDownRight, ArrowUpRight, Bell, CircleHelp, RefreshCw, ScanSearch, Settings2, ShieldCheck, WalletCards } from 'lucide-react'

type Opportunity = {
  id: string; asset: string; fiat: string; buy_exchange: string; sell_exchange: string
  buy_price: number; sell_price: number; buy_ad_min_fiat: number; buy_ad_max_fiat: number
  sell_ad_min_fiat: number; sell_ad_max_fiat: number; buy_payment_methods: string[]
  sell_payment_methods: string[]; buy_advertiser_completion_pct: number
  sell_advertiser_completion_pct: number; remaining_crypto: number; source_updated_at: string
  source_mode: 'demo' | 'live'
}
type ScanResponse = { mode: 'demo' | 'live' | 'unavailable'; updated_at: string; opportunities: Opportunity[]; message?: string; warnings?: string[] }

const fmt = (n: number, fiat: string) => new Intl.NumberFormat('ru-RU', {
  style: 'currency', currency: fiat, maximumFractionDigits: fiat === 'RUB' ? 2 : 4
}).format(n)

export default function App() {
  const [asset, setAsset] = useState('USDT')
  const [fiat, setFiat] = useState('RUB')
  const [capital, setCapital] = useState(50000)
  const [feePct, setFeePct] = useState(0.2)
  const [minSpread, setMinSpread] = useState(1)
  const [data, setData] = useState<ScanResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const scan = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await fetch(`/api/opportunities?asset=${encodeURIComponent(asset)}&fiat=${encodeURIComponent(fiat)}&capital=${capital}`)
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      setData(await res.json())
    } catch {
      setError('Не удалось связаться с API. Запусти backend по инструкции в README.')
      setData(null)
    } finally { setLoading(false) }
  }, [asset, fiat, capital])

  useEffect(() => { void scan() }, [scan])

  const rows = useMemo(() => (data?.opportunities ?? []).map(o => {
    const spend = Math.min(capital, o.buy_ad_max_fiat, o.sell_ad_max_fiat)
    const qty = Math.min(spend / o.buy_price, o.remaining_crypto)
    const usedCapital = qty * o.buy_price
    const gross = qty * (o.sell_price - o.buy_price)
    const estimatedFees = usedCapital * feePct / 100
    const net = gross - estimatedFees
    const spread = usedCapital > 0 ? net / usedCapital * 100 : 0
    return { ...o, usedCapital, qty, gross, estimatedFees, net, spread }
  }).filter(o => o.spread >= minSpread && o.sell_price > o.buy_price)
    .sort((a, b) => b.spread - a.spread), [data, capital, feePct, minSpread])

  return <main className="app-shell">
    <header className="topbar">
      <div className="brand-mark"><ScanSearch size={23}/></div>
      <div className="brand-copy"><div className="brand-name">SPREAD<span>SCANNER</span></div><div className="brand-sub">P2P ARBITRAGE TERMINAL</div></div>
      <span className={`mode-pill ${data?.mode === 'live' ? 'live' : ''}`}><i />{data?.mode === 'live' ? 'LIVE' : data?.mode === 'unavailable' ? 'OFFLINE' : data?.mode === 'demo' ? 'DEMO' : 'CONNECTING'}</span>
    </header>

    <section className="hero">
      <div className="eyebrow"><Activity size={14}/> MARKET OVERVIEW</div>
      <h1>Находи спред.<br/><em>Считай прибыль.</em></h1>
      <p>Bybit P2P · RUB · банковские переводы · межбиржевой режим включится после добавления второй биржи.</p>
    </section>

    <section className="stats-grid">
      <div className="stat-card featured">
        <div className="stat-label">ЛУЧШИЙ ЧИСТЫЙ СПРЕД</div>
        <div className="stat-value">{rows.length ? `${rows[0].spread.toFixed(2)}%` : '—'}</div>
        <div className="stat-foot"><ArrowUpRight size={14}/> После указанной комиссии</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">ПРИБЫЛЬ ОЦЕНКА</div>
        <div className="stat-value">{rows.length ? fmt(rows[0].net, fiat) : '—'}</div>
        <div className="stat-foot muted">На выбранный капитал</div>
      </div>
    </section>

    <section className="panel">
      <div className="section-heading"><div><span className="section-kicker">01 / CONFIG</span><h2>Параметры сканирования</h2></div><Settings2 size={19}/></div>
      <div className="field-grid">
        <label>КРИПТОАКТИВ<select value={asset} onChange={e => setAsset(e.target.value)}><option>USDT</option><option>BTC</option></select></label>
        <label>ФИАТ<select value={fiat} onChange={e => setFiat(e.target.value)}><option>RUB</option></select></label>
      </div>
      <label className="field-label">КАПИТАЛ <strong>{fmt(capital, fiat)}</strong></label>
      <input type="range" min={1000} max={500000} step={1000} value={capital} onChange={e => setCapital(Number(e.target.value))}/>
      <div className="range-labels"><span>1 000</span><span>500 000</span></div>
      <div className="field-grid lower-fields">
        <label>КОМИССИИ, %<input type="number" min="0" max="10" step="0.05" value={feePct} onChange={e => setFeePct(Math.max(0, Number(e.target.value)))}/></label>
        <label>МИН. СПРЕД, %<input type="number" min="-100" max="100" step="0.1" value={minSpread} onChange={e => setMinSpread(Number(e.target.value))}/></label>
      </div>
      <button className="scan-button" onClick={() => void scan()} disabled={loading}>{loading ? <RefreshCw className="spin" size={17}/> : <ScanSearch size={17}/>} {loading ? 'Сканирование…' : 'Обновить возможности'}</button>
    </section>

    <section className="opportunities">
      <div className="list-heading"><div><span className="section-kicker">02 / OPPORTUNITIES</span><h2>Найденные связки <span className="count">{rows.length}</span></h2></div><button className="icon-button" onClick={() => void scan()} aria-label="Обновить"><RefreshCw size={17}/></button></div>
       {error && <div className="error-box">{error}</div>}
      {data?.mode === 'unavailable' && <div className="error-box"><strong>Реальные котировки недоступны.</strong><br/>{data.message}<br/><small>Демо-данные не подставляются.</small></div>}
      {data?.warnings?.map(w => <div className="warning-box" key={w}>{w}</div>)}
      {!error && data?.mode === 'live' && rows.length === 0 && !loading && <div className="empty-state">Подходящих связок не найдено. Проверь способ оплаты, лимиты объявлений или доступность P2P-рынка.</div>}
      {rows.map((o, i) => <article className="opportunity-card" key={o.id}>
        <div className="opp-top">
          <div className="coin-icon">{o.asset === 'BTC' ? '₿' : '₮'}</div>
          <div className="pair-copy"><strong>{o.asset}<span> / {o.fiat}</span></strong><small>{o.buy_exchange} → {o.sell_exchange}</small></div>
          <div className="spread-chip"><b>{o.spread.toFixed(2)}%</b><small>NET SPREAD</small></div>
        </div>
        <div className="price-flow">
          <div><small><ArrowDownRight size={13}/> КУПИТЬ</small><strong>{fmt(o.buy_price, fiat)}</strong><span>{o.buy_exchange}</span></div>
          <div className="flow-arrow">→</div>
          <div><small><ArrowUpRight size={13}/> ПРОДАТЬ</small><strong>{fmt(o.sell_price, fiat)}</strong><span>{o.sell_exchange}</span></div>
        </div>
        <div className="opp-divider"/>
        <div className="profit-row"><span>Оценка чистой прибыли</span><strong>{fmt(o.net, fiat)}</strong></div>
        <div className="details-row"><span><WalletCards size={13}/> Объём: {o.qty.toFixed(o.asset === 'BTC' ? 6 : 2)} {o.asset}</span><span><ShieldCheck size={13}/> Исполнение: {Math.min(o.buy_advertiser_completion_pct, o.sell_advertiser_completion_pct).toFixed(1)}%</span></div>
        <div className="payment-tags">{[...new Set([...o.buy_payment_methods, ...o.sell_payment_methods])].map(p => <span key={p}>{p}</span>)}</div>
        <div className="fine-print">Расчётная оценка. Проверь лимиты и доступность объявлений перед сделкой.</div>
      </article>)}
    </section>

    <footer><div className="footer-icon"><Bell size={15}/></div><div><strong>Сигналы о спреде</strong><p>Следующий этап — Telegram-уведомления по заданному порогу.</p></div><CircleHelp size={17} className="help-icon"/></footer>
    <div className="bottom-note">LIVE DATA ONLY WHEN API AUTHENTICATED · РАСЧЁТНАЯ ОЦЕНКА, НЕ ФИНАНСОВАЯ РЕКОМЕНДАЦИЯ</div>
  </main>
}
