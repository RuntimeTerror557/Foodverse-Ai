import { type ReactNode, type CSSProperties, type FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Route, Switch, useLocation, Router as WouterRouter, Link } from 'wouter';
import {
  Activity, AlertTriangle, Apple, ArrowDownRight, ArrowRight, ArrowUpRight,
  AudioLines, Bell, ChefHat, Check, CheckCircle2, ChevronDown, CircleHelp,
  Clock3, CloudUpload, CookingPot, Download, Droplets, Flame, Gauge,
  HeartPulse, Home, Leaf, ListChecks, Menu, Moon, MoreHorizontal, Play,
  Plus, ScanLine, Search, ShieldCheck, ShoppingBasket, Sparkles, Sun,
  Utensils, Video, Wheat, X,
} from 'lucide-react';
import {
  useHealthCheck, useGetDashboard, getGetDashboardQueryKey,
  useListScans, getListScansQueryKey, useScanFood, useDetectFreshness,
  useListAudits, getListAuditsQueryKey, useAnalyzeHygiene,
  useGetProfile, getGetProfileQueryKey, useSaveProfile,
  useGetMealPlan, getGetMealPlanQueryKey, useGenerateMealPlan,
  useUpdateMealCompletion, useUpdateGroceryItem, useCreateChefGuide,
} from '@workspace/api-client-react';
import type { FoodScan, HygieneAudit, MealPlan, NutritionProfile, ChefGuide } from '@workspace/api-client-react';

const queryClient = new QueryClient();
const navItems = [
  { href: '/', label: 'Overview', icon: Home },
  { href: '/scanner', label: 'Food scanner', icon: ScanLine },
  { href: '/hygiene', label: 'Kitchen hygiene', icon: ShieldCheck },
  { href: '/chef', label: 'AI chef', icon: ChefHat },
  { href: '/planner', label: 'Meal planner', icon: ListChecks },
];
const titleMap: Record<string, string> = {
  '/': 'Overview', '/scanner': 'Food scanner', '/hygiene': 'Kitchen hygiene',
  '/chef': 'AI chef', '/planner': 'Meal planner', '/profile': 'Your profile',
};
const pretty = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

type VoiceRecognitionResult = { 0: { transcript: string } };
type VoiceRecognitionLike = {
  lang: string;
  interimResults: boolean;
  onresult: ((event: { results: ArrayLike<VoiceRecognitionResult> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function AppShell({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const [dark, setDark] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const health = useHealthCheck();
  useEffect(() => {
    const saved = localStorage.getItem('fv-theme') === 'dark';
    setDark(saved);
    document.documentElement.classList.toggle('dark', saved);
  }, []);
  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('fv-theme', next ? 'dark' : 'light');
  };
  return <div className="app-frame">
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <Link href="/" className="brand" data-testid="link-brand">
        <span className="brand-mark"><Leaf size={20} strokeWidth={2.2} /></span>
        <span className="brand-type">food<span>verse</span><small>INTELLIGENCE, AT HOME</small></span>
      </Link>
      <div className="side-caption">YOUR FOODSPACE</div>
      <nav className="side-nav" aria-label="Main navigation">
        {navItems.map(({ href, label, icon: Icon }) => <Link key={href} href={href}
          onClick={() => setMobileOpen(false)} className={`nav-link ${location === href ? 'active' : ''}`}
          data-testid={`link-${href === '/' ? 'overview' : href.slice(1)}`}>
          <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{href === '/scanner' && <span className="nav-new">AI</span>}
        </Link>)}
      </nav>
      <div className="side-spacer" />
      <div className="side-plan">
        <span className="plan-icon"><Sparkles size={16} /></span>
        <strong>Your week, in balance</strong>
        <p>Small choices add up to a better-feeling you.</p>
        <Link href="/planner" className="plan-link" data-testid="link-plan-week">See your plan <ArrowRight size={14} /></Link>
      </div>
      <Link href="/profile" className={`nav-link profile-link ${location === '/profile' ? 'active' : ''}`} data-testid="link-profile">
        <span className="avatar">M</span><span>My preferences</span><ChevronDown size={15} className="profile-chevron" />
      </Link>
      <div className="sidebar-foot"><span className={`health-dot ${health.isError ? 'offline' : ''}`} /> {health.isError ? 'Offline mode' : 'Your kitchen, considered'}</div>
    </aside>
    {mobileOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <main className="main-area">
      <header className="topbar">
        <button className="icon-button mobile-menu" aria-label="Open navigation" data-testid="button-open-nav" onClick={() => setMobileOpen(!mobileOpen)}><Menu size={19} /></button>
        <div className="breadcrumbs"><span>Food verse</span><span className="crumb-slash">/</span><strong>{titleMap[location] ?? 'Overview'}</strong></div>
        <div className="top-actions">
          <span className="today-label">{new Intl.DateTimeFormat('en', { weekday: 'long', month: 'short', day: 'numeric' }).format(new Date())}</span>
          <button className="icon-button theme-toggle" title={`Switch to ${dark ? 'light' : 'dark'} mode`} aria-label="Toggle dark mode" data-testid="button-theme-toggle" onClick={toggleTheme}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
          <button className="icon-button notification-button" aria-label="Notifications" data-testid="button-notifications"><Bell size={18} /><i /></button>
          <Link href="/profile" className="top-avatar" aria-label="Profile" data-testid="link-profile-avatar">M</Link>
        </div>
      </header>
      <div className="page-content">{children}</div>
    </main>
  </div>;
}

function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action && <div className="heading-action">{action}</div>}</div>;
}
function LoadingCards() { return <div className="loading-grid" aria-label="Loading"><div className="skeleton skeleton-lg" /><div className="skeleton" /><div className="skeleton" /></div>; }
function ErrorNotice({ retry }: { retry: () => void }) { return <div className="error-notice" role="alert"><AlertTriangle size={18} /><span>We couldn't load this just now.</span><button onClick={retry} className="text-button" data-testid="button-retry">Try again</button></div>; }
function StatCard({ label, value, unit, icon: Icon, tone = 'green', foot }: { label: string; value: string | number; unit?: string; icon: typeof Flame; tone?: string; foot?: string }) {
  return <div className="stat-card" data-testid={`stat-${label.toLowerCase().replaceAll(' ', '-')}`}><div className={`stat-icon ${tone}`}><Icon size={18} /></div><span className="stat-label">{label}</span><div className="stat-value">{value}<small>{unit}</small></div>{foot && <div className="stat-foot">{foot}</div>}</div>;
}
function Ring({ value, label, sub }: { value: number; label: string; sub: string }) {
  return <div className="ring-wrap"><div className="progress-ring" style={{ '--progress': `${Math.min(value, 100)}%` } as CSSProperties}><div><strong>{value}</strong><small>/ 100</small></div></div><div><span className="ring-label">{label}</span><p>{sub}</p></div></div>;
}
function Dashboard() {
  const dashboard = useGetDashboard();
  const scans = useListScans();
  const data = dashboard.data;
  const recent = scans.data ?? [];
  if (dashboard.isLoading) return <LoadingCards />;
  if (dashboard.isError || !data) return <ErrorNotice retry={() => void dashboard.refetch()} />;
  const pct = Math.min(Math.round(data.caloriesConsumed / Math.max(data.calorieTarget, 1) * 100), 100);
  return <>
    <PageHeading eyebrow="MONDAY, MADE MEANINGFUL" title="A little more in balance." description="Your daily food picture, thoughtfully brought together." action={<Link href="/scanner" className="button button-primary" data-testid="button-start-scan"><ScanLine size={16} /> Scan something</Link>} />
    <section className="welcome-banner">
      <div className="welcome-copy"><div className="welcome-kicker"><span className="sparkle-dot" /> YOUR DAILY CHECK-IN</div><h2>Good food choices<br />are already <em>in motion.</em></h2><p>A quick look at what’s nourishing you today.</p><Link href="/planner" className="welcome-cta" data-testid="link-todays-plan">View today’s plan <ArrowRight size={16} /></Link></div>
      <div className="welcome-art" aria-hidden="true"><div className="art-sun" /><div className="art-plate"><span /><span /><span /><span /><i /></div><div className="art-leaf leaf-a" /><div className="art-leaf leaf-b" /><div className="art-grain" /></div>
      <div className="banner-note"><span>WELLNESS SCORE</span><strong>{data.healthScore}<small>/100</small></strong><div className="mini-meter"><i style={{ width: `${data.healthScore}%` }} /></div><small>Steady, thoughtful progress</small></div>
    </section>
    <div className="section-row"><div><div className="eyebrow">TODAY AT A GLANCE</div><h2 className="section-title">Your nutrition, in focus</h2></div><Link href="/profile" className="subtle-link" data-testid="link-update-goals">Edit goals <ArrowRight size={14} /></Link></div>
    <section className="stats-grid">
      <StatCard label="Calories" value={data.caloriesConsumed.toLocaleString()} unit="kcal" icon={Flame} tone="amber" foot={`${pct}% of ${data.calorieTarget.toLocaleString()} daily goal`} />
      <StatCard label="Protein" value={`${data.proteinConsumed}`} unit="g" icon={Activity} tone="mint" foot="A strong foundation for today" />
      <StatCard label="Carbohydrates" value={`${data.carbsConsumed}`} unit="g" icon={Wheat} tone="ochre" foot="Energy for your day" />
      <StatCard label="Meals logged" value={`${data.mealsLogged}`} unit={`of ${data.mealsPlanned}`} icon={Utensils} tone="slate" foot="One plate at a time" />
    </section>
    <section className="dashboard-lower">
      <div className="panel nutrition-panel">
        <div className="panel-heading"><div><div className="eyebrow">DAILY RHYTHM</div><h3>Calories in context</h3></div><button className="quiet-button" data-testid="button-weekly-view">This week <ChevronDown size={14} /></button></div>
        <div className="calorie-number"><strong>{data.caloriesConsumed.toLocaleString()}</strong><span> / {data.calorieTarget.toLocaleString()} kcal</span><span className="trend-up"><ArrowUpRight size={14} /> on track</span></div>
        <div className="calorie-track"><span style={{ width: `${pct}%` }} /></div>
        <div className="chart-area"><div className="chart-y"><span>2,000</span><span>1,000</span><span>0</span></div><div className="bar-chart">{(data.weeklyCalories ?? []).map((n, i) => <div className="bar-column" key={`day-${i}`}><div className={`chart-bar ${i === Math.min(new Date().getDay(), 6) ? 'bar-today' : ''}`} style={{ height: `${Math.max(n / Math.max(data.calorieTarget, 1) * 100, 7)}%` }} title={`${n} kcal`} /><small>{['M', 'T', 'W', 'T', 'F', 'S', 'S'][i]}</small></div>)}</div></div>
        <div className="chart-legend"><span><i /> Daily intake</span><span className="goal-line" /> Your daily target</div>
      </div>
      <div className="panel insight-panel">
        <div className="panel-heading"><div><div className="eyebrow">A THOUGHTFUL NUDGE</div><h3>Small things, noticed</h3></div><span className="insight-icon"><Sparkles size={17} /></span></div>
        <div className="insight-main"><div className="insight-illustration"><Droplets size={22} /><span /></div><div><span className="insight-tag">NUTRITION NOTE</span><h4>A little more fiber?</h4><p>Today’s plate is a touch light on fiber. Lentils, berries, or a handful of almonds can bring it into balance.</p></div></div>
        <Link href="/planner" className="insight-link" data-testid="link-fiber-ideas">Find an idea for today <ArrowRight size={15} /></Link>
        <div className="insight-divider" /><div className="next-meal"><div className="meal-time"><Clock3 size={15} /><span>UP NEXT · {data.nextMeal?.slot ?? 'LUNCH'}</span></div><strong>{data.nextMeal?.name ?? 'A nourishing plate'}</strong><span>{data.nextMeal?.calories ?? '—'} kcal <i>·</i> {data.nextMeal?.protein ?? '—'}g protein</span><Link href="/planner" aria-label="Open meal plan" data-testid="link-next-meal"><ArrowRight size={17} /></Link></div>
      </div>
    </section>
    <section className="recent-section">
      <div className="section-row"><div><div className="eyebrow">YOUR FOOD JOURNAL</div><h2 className="section-title">Recent scans</h2></div><Link href="/scanner" className="subtle-link" data-testid="link-all-scans">Explore all scans <ArrowRight size={14} /></Link></div>
      {scans.isLoading ? <div className="skeleton skeleton-row" /> : scans.isError ? <ErrorNotice retry={() => void scans.refetch()} /> : recent.length ? <div className="scan-list">{recent.slice(0, 4).map(scan => <ScanRow key={scan.id} scan={scan} />)}</div> : <EmptyState icon={ScanLine} title="Your food story starts here" text="Scan your first plate for a clearer picture of what’s on it." link="/scanner" linkText="Scan a meal" />}
    </section>
  </>;
}
function ScanRow({ scan }: { scan: FoodScan }) {
  return <div className="scan-row" data-testid={`row-scan-${scan.id}`}><div className="scan-thumb"><Apple size={19} /></div><div className="scan-detail"><strong>{scan.dishName}</strong><span>{new Date(scan.createdAt).toLocaleDateString('en', { month: 'short', day: 'numeric' })} <i>·</i> {scan.ingredients.slice(0, 3).join(', ')}</span></div><div className="scan-kcal"><strong>{scan.nutrition.calories}</strong><span>kcal</span></div><span className={`freshness-pill ${scan.freshness.status}`}>{scan.freshness.label}</span><span className="health-score">{scan.healthScore}<small> health</small></span><button className="icon-button small-icon" aria-label={`More about ${scan.dishName}`} data-testid={`button-scan-details-${scan.id}`}><MoreHorizontal size={18} /></button></div>;
}
function EmptyState({ icon: Icon, title, text, link, linkText }: { icon: typeof ScanLine; title: string; text: string; link: string; linkText: string }) {
  return <div className="empty-state"><span><Icon size={22} /></span><h3>{title}</h3><p>{text}</p><Link className="button button-outline" href={link} data-testid={`link-empty-${link.slice(1) || 'home'}`}>{linkText} <ArrowRight size={15} /></Link></div>;
}

function ScannerPage() {
  const queryClient = useQueryClient();
  const scans = useListScans();
  const scanMutation = useScanFood();
  const freshnessMutation = useDetectFreshness();
  const [source, setSource] = useState<'image' | 'video' | 'audio' | 'text'>('image');
  const [description, setDescription] = useState('');
  const [fileNames, setFileNames] = useState<Record<'image' | 'video' | 'audio' | 'text', string>>({ image: '', video: '', audio: '', text: '' });
  const fileName = fileNames[source];
  const setFileName = (name: string) => setFileNames(previous => ({ ...previous, [source]: name }));
  const [freshFood, setFreshFood] = useState('');
  const [freshNotes, setFreshNotes] = useState('');
  const [freshResult, setFreshResult] = useState<FoodScan['freshness'] | null>(null);
  const [selected, setSelected] = useState<FoodScan | null>(null);
  const [mediaError, setMediaError] = useState('');
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<VoiceRecognitionLike | null>(null);
  const onFile = (file?: File) => {
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) { setMediaError('Choose a file smaller than 20 MB.'); return; }
    const validType = source === 'image' ? file.type.startsWith('image/') : source === 'video' ? file.type.startsWith('video/') : source === 'audio' ? file.type.startsWith('audio/') : true;
    if (!validType) { setMediaError(`Choose a ${source} file.`); return; }
    setMediaError('');
    setFileName(file.name);
    if (!description.trim()) setDescription(file.name.replace(/\.[^.]+$/, '').replaceAll(/[-_]/g, ' '));
  };
  const startVoiceQuery = () => {
    const speech = window as unknown as { SpeechRecognition?: new () => VoiceRecognitionLike; webkitSpeechRecognition?: new () => VoiceRecognitionLike };
    const SpeechRecognition = speech.SpeechRecognition ?? speech.webkitSpeechRecognition;
    if (!SpeechRecognition) { setMediaError('Voice transcription is not available in this browser. You can upload an audio file or type your question.'); return; }
    const recognition = new SpeechRecognition();
    recognition.lang = navigator.language || 'en-US';
    recognition.interimResults = false;
    recognition.onresult = event => {
      const transcript = Array.from(event.results).map(result => result[0].transcript).join(' ').trim();
      if (transcript) setDescription(transcript);
    };
    recognition.onerror = () => { setListening(false); setMediaError('Microphone access was unavailable. You can upload audio or type your question.'); };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setSource('audio');
    setMediaError('');
    setListening(true);
    recognition.start();
  };
  const stopVoiceQuery = () => { recognitionRef.current?.stop(); setListening(false); };
  const runScan = () => scanMutation.mutate({ data: { source, fileName: fileName || null, description } }, { onSuccess: (scan) => { setSelected(scan); void queryClient.invalidateQueries({ queryKey: getListScansQueryKey() }); void queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() }); } });
  const runFreshness = () => freshnessMutation.mutate({ data: { food: freshFood, fileName: fileName || null, notes: freshNotes } }, { onSuccess: setFreshResult });
  return <>
    <PageHeading eyebrow="SEE WHAT'S ON YOUR PLATE" title="Know your food, better." description="A photo or a few words can bring more clarity to every meal." />
    <div className="scanner-layout">
      <div className="panel scan-workspace">
        <div className="scanner-tabs">
          <button className={source === 'image' ? 'selected' : ''} onClick={() => setSource('image')} data-testid="tab-scan-image"><ScanLine size={15} /> Photo</button>
          <button className={source === 'video' ? 'selected' : ''} onClick={() => setSource('video')} data-testid="tab-scan-video"><Video size={15} /> Video</button>
          <button className={source === 'audio' ? 'selected' : ''} onClick={() => setSource('audio')} data-testid="tab-scan-audio"><AudioLines size={15} /> Voice</button>
          <button className={source === 'text' ? 'selected' : ''} onClick={() => setSource('text')} data-testid="tab-scan-text"><Utensils size={15} /> Text</button>
        </div>
        {source !== 'text' && <label className="upload-zone" htmlFor="food-upload" data-testid={`dropzone-food-${source}`} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); onFile(event.dataTransfer.files?.[0]); }}>
          <span className="upload-graphic"><CloudUpload size={23} /></span>
          <strong>{fileName || (source === 'image' ? 'Drop a food photo here' : source === 'video' ? 'Drop a food video here' : 'Drop an audio clip here')}</strong>
          <span>or choose a {source} file from your device</span>
          <small>{source === 'image' ? 'JPG, PNG or WEBP' : source === 'video' ? 'MP4, MOV or WEBM' : 'MP3, WAV or M4A'} · up to 20 MB</small>
          <input id="food-upload" type="file" accept={source === 'image' ? 'image/*' : source === 'video' ? 'video/*' : 'audio/*'} onChange={e => onFile(e.target.files?.[0])} data-testid={`input-food-${source}`} />
        </label>}
        {source === 'audio' && <button className={`voice-capture ${listening ? 'capturing' : ''}`} onClick={listening ? stopVoiceQuery : startVoiceQuery} data-testid="button-record-food-query"><AudioLines size={16} />{listening ? 'Stop listening' : 'Ask by voice'}<span>{listening ? 'Listening…' : 'Uses your browser microphone'}</span></button>}
        {mediaError && <div className="inline-error" role="alert">{mediaError}</div>}
        <label className="field-label" htmlFor="meal-description">{source === 'audio' ? 'Your voice question or transcript' : source === 'image' ? 'Add a little context' : source === 'video' ? 'Describe the food shown' : 'What’s on your plate?'}</label>
        <textarea id="meal-description" value={description} onChange={e => setDescription(e.target.value)} placeholder="For example: roasted salmon with quinoa, greens and lemon..." rows={3} maxLength={1000} data-testid="input-meal-description" />
        <div className="form-foot"><span>{description.length}/1000</span><button className="button button-primary" disabled={!description.trim() || scanMutation.isPending} onClick={runScan} data-testid="button-analyze-food"><ScanLine size={16} /> {scanMutation.isPending ? 'Looking closer…' : 'Analyze this meal'} <ArrowRight size={15} /></button></div>
        {scanMutation.isError && <div className="inline-error" role="alert">We couldn’t complete that scan. Please try again.</div>}
        <p className="estimate-note"><CircleHelp size={14} /> Demo estimates use your description and filename. Media stays in this browser; results are not medical advice.</p>
      </div>
      {selected ? <div className="panel result-panel">
        <div className="result-top"><div><div className="eyebrow">YOUR FOOD SNAPSHOT</div><h2>{selected.dishName}</h2></div><button className="icon-button" aria-label="Close results" onClick={() => setSelected(null)} data-testid="button-close-scan-results"><X size={18} /></button></div>
        <Ring value={selected.healthScore} label="Health score" sub={`${selected.confidence}% match confidence`} />
        <div className="macro-grid"><div><span>Energy</span><strong>{selected.nutrition.calories}<small> kcal</small></strong></div><div><span>Protein</span><strong>{selected.nutrition.protein}<small> g</small></strong></div><div><span>Carbs</span><strong>{selected.nutrition.carbs}<small> g</small></strong></div><div><span>Fat</span><strong>{selected.nutrition.fat}<small> g</small></strong></div></div>
        <div className="scan-nutrients"><div className="fiber-value"><span>Fiber</span><strong>{selected.nutrition.fiber}<small> g</small></strong></div><div className="micronutrients"><span className="mini-heading">POSSIBLE MICRONUTRIENTS</span><div className="tag-list">{selected.nutrition.micronutrients.map(item => <span key={item}>{item}</span>)}</div></div></div>
        <div className="score-signals"><div className="signal-heading"><span className="mini-heading">HEALTH SCORE SIGNALS</span><small>Illustrative demo breakdown</small></div>{selected.healthBreakdown.map(signal => <div className="score-signal" key={signal.label} data-testid={`signal-${signal.label.toLowerCase().replaceAll(' ', '-')}`}><div><span>{signal.label}</span><strong>{signal.score}</strong></div><div className="signal-track" role="progressbar" aria-label={signal.label} aria-valuenow={signal.score} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${signal.score}%` }} /></div><small>{signal.detail}</small></div>)}</div>
        <div className="ingredient-wrap"><span className="mini-heading">POSSIBLE INGREDIENTS</span><div className="tag-list">{selected.ingredients.map(item => <span key={item}>{item}</span>)}</div></div>
        <div className={`freshness-result ${selected.freshness.status}`}><ShieldCheck size={18} /><div><strong>{selected.freshness.label}</strong><p>{selected.freshness.guidance}</p></div></div>
      </div> : <div className="scanner-aside"><div className="aside-nutrition"><span className="eyebrow">A CLEARER PICTURE</span><h3>Insight for the<br />everyday plate.</h3><p>Get a thoughtful estimate of nutrition, ingredients, and food freshness in one place.</p><div className="circle-food"><div className="food-dot fd-one" /><div className="food-dot fd-two" /><div className="food-dot fd-three" /><div className="food-dot fd-four" /><div className="food-dot fd-five" /><span>FV</span></div><div className="aside-features"><span><Check size={14} /> Nutrition overview</span><span><Check size={14} /> Ingredient cues</span><span><Check size={14} /> Freshness estimate</span></div></div>
        <div className="freshness-card">
          <div className="freshness-card-head"><div className="freshness-mini-icon"><ShieldCheck size={17} /></div><div><strong>Freshness check</strong><span>Quickly check what’s in the fridge</span></div></div>
          <div className="freshness-input"><input value={freshFood} onChange={e => setFreshFood(e.target.value)} placeholder="e.g. opened oat milk" aria-label="Food to check for freshness" data-testid="input-freshness-food" /><button disabled={!freshFood.trim() || freshnessMutation.isPending} aria-label="Check freshness" onClick={runFreshness} data-testid="button-check-freshness"><ArrowRight size={16} /></button></div>
          <input className="freshness-cues" value={freshNotes} onChange={e => setFreshNotes(e.target.value)} placeholder="Visible color, texture, smell, or storage notes" aria-label="Freshness cues" data-testid="input-freshness-cues" />
          {freshnessMutation.isError && <p className="inline-error">Freshness check unavailable. Please try again.</p>}
          {freshResult && <div className={`freshness-result ${freshResult.status}`}><ShieldCheck size={17} /><div><strong>{freshResult.label}</strong><p>{freshResult.guidance}</p><small>{freshResult.storageTip}</small></div></div>}
          <small className="estimate-note"><CircleHelp size={13} /> A description-based estimate, not a safety guarantee.</small>
        </div>
      </div>}
    </div>
    <section className="recent-section"><div className="section-row"><div><div className="eyebrow">YOUR JOURNAL</div><h2 className="section-title">Recent food scans</h2></div><span className="count-label">{scans.data?.length ?? 0} entries</span></div>{scans.isLoading ? <div className="skeleton skeleton-row" /> : scans.isError ? <ErrorNotice retry={() => void scans.refetch()} /> : scans.data?.length ? <div className="scan-list">{scans.data.map(scan => <ScanRow key={scan.id} scan={scan} />)}</div> : <EmptyState icon={ScanLine} title="Nothing scanned yet" text="Your first scan will appear here, ready whenever you need a quick reference." link="/scanner" linkText="Start a scan" />}</section>
  </>;
}

function HygienePage() {
  const qc = useQueryClient();
  const audits = useListAudits();
  const mutation = useAnalyzeHygiene();
  const [kitchen, setKitchen] = useState('My kitchen');
  const [fileName, setFileName] = useState('');
  const [audit, setAudit] = useState<HygieneAudit | null>(null);
  const run = (mode: 'sample' | 'upload') => mutation.mutate({ data: { kitchenName: kitchen, videoName: fileName || null, mode } }, { onSuccess: (result) => { setAudit(result); void qc.invalidateQueries({ queryKey: getListAuditsQueryKey() }); } });
  const download = () => {
    if (!audit) return;
    const text = `Food Verse AI — Kitchen hygiene estimate\n${audit.kitchenName}\nSafety score: ${audit.safetyScore}/100\nCleanliness: ${audit.cleanlinessScore}/100\nGlove compliance: ${audit.gloveCompliance}%\nHairnet compliance: ${audit.hairnetCompliance}%\nContamination risk: ${audit.contaminationRisk}\n\nAlerts:\n${audit.alerts.map(a => `• ${a}`).join('\n')}\n\nThis is an AI-generated estimate, not a real safety certification.`;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'food-verse-kitchen-scorecard.txt'; anchor.click(); URL.revokeObjectURL(url);
  };
  return <>
    <PageHeading eyebrow="A SAFER SPACE TO COOK" title="Care starts in the kitchen." description="A video-based kitchen hygiene review to help spot habits worth a second look." action={<span className="estimate-badge"><CircleHelp size={14} /> Estimate only</span>} />
    <div className="hygiene-grid">
      <div className="panel audit-start"><div className="audit-symbol"><ShieldCheck size={24} /></div><span className="eyebrow">KITCHEN VIDEO AUDIT</span><h2>Small routines.<br /><em>Safer meals.</em></h2><p>Review common hygiene cues like hand protection, hair coverage, and surface cleanliness.</p>
        <label className="field-label" htmlFor="kitchen-name">Kitchen name</label><input id="kitchen-name" className="text-input" value={kitchen} onChange={e => setKitchen(e.target.value)} maxLength={120} data-testid="input-kitchen-name" />
        <label className="field-label">Add a short kitchen video <span>(optional)</span></label><label className="video-upload" htmlFor="kitchen-video"><Video size={19} /><span>{fileName || 'Choose a video to review'}</span><input id="kitchen-video" type="file" accept="video/*" onChange={e => setFileName(e.target.files?.[0]?.name ?? '')} data-testid="input-kitchen-video" /><Plus size={16} /></label>
        <button className="button button-primary full-button" disabled={!kitchen.trim() || mutation.isPending} onClick={() => run(fileName ? 'upload' : 'sample')} data-testid="button-run-audit"><ShieldCheck size={17} />{mutation.isPending ? 'Reviewing kitchen…' : fileName ? 'Review video' : 'Run sample review'}<ArrowRight size={15} /></button>{mutation.isError && <div className="inline-error" role="alert">We couldn’t create this review. Try again.</div>}
        <p className="estimate-note"><CircleHelp size={14} /> AI-generated guidance is an estimate—not a food-safety certification.</p>
      </div>
      <div className="panel audit-overview">
        {audit ? <><div className="panel-heading"><div><div className="eyebrow">YOUR LATEST ESTIMATE</div><h3>{audit.kitchenName}</h3></div><span className="audit-score">{audit.safetyScore}<small>/100</small></span></div><div className="audit-scorebar"><span style={{ width: `${audit.safetyScore}%` }} /></div><div className="audit-metrics"><div><span>Surface cleanliness</span><strong>{audit.cleanlinessScore}<small>%</small></strong></div><div><span>Glove compliance</span><strong>{audit.gloveCompliance}<small>%</small></strong></div><div><span>Hair coverage</span><strong>{audit.hairnetCompliance}<small>%</small></strong></div></div><div className={`risk-band risk-${audit.contaminationRisk}`}><AlertTriangle size={16} /><span><strong>{pretty(audit.contaminationRisk)} contamination risk</strong><small>Based on visible hygiene indicators</small></span></div><div className="alerts-list"><span className="mini-heading">OBSERVATIONS</span>{audit.alerts.length ? audit.alerts.map((alert, i) => <div key={`${i}-${alert}`}><span>{String(i + 1).padStart(2, '0')}</span>{alert}</div>) : <p>No observations were noted in this review.</p>}</div><button className="button button-outline full-button" onClick={download} data-testid="button-download-scorecard"><Download size={16} /> Download scorecard</button></> : <div className="audit-empty"><div className="audit-orbit"><div><ShieldCheck size={28} /></div><span /><span /><span /></div><h3>Your kitchen snapshot</h3><p>Run your first review to see a scorecard of visible hygiene indicators and practical observations.</p><div className="audit-check-list"><span><CheckCircle2 size={15} /> Food handling cues</span><span><CheckCircle2 size={15} /> Surface cleanliness</span><span><CheckCircle2 size={15} /> Practical observations</span></div></div>}
      </div>
    </div>
    <section className="recent-section"><div className="section-row"><div><div className="eyebrow">PAST REVIEWS</div><h2 className="section-title">Kitchen history</h2></div></div>{audits.isLoading ? <div className="skeleton skeleton-row" /> : audits.isError ? <ErrorNotice retry={() => void audits.refetch()} /> : audits.data?.length ? <div className="audit-history">{audits.data.map(item => <div key={item.id} className="history-row" data-testid={`row-audit-${item.id}`}><div className="history-icon"><ShieldCheck size={17} /></div><div><strong>{item.kitchenName}</strong><span>{new Date(item.createdAt).toLocaleDateString()} · {pretty(item.contaminationRisk)} risk</span></div><b>{item.safetyScore}<small>/100</small></b></div>)}</div> : <EmptyState icon={ShieldCheck} title="No kitchen reviews yet" text="When you run a review, your estimate history will be kept here." link="/hygiene" linkText="Start a review" />}</section>
  </>;
}

function ChefPage() {
  const profile = useGetProfile();
  const scans = useListScans();
  const createGuide = useCreateChefGuide();
  const [dish, setDish] = useState('');
  const [ingredientsText, setIngredientsText] = useState('');
  const [guide, setGuide] = useState<ChefGuide | null>(null);
  const [activeStep, setActiveStep] = useState(0);
  const [speaking, setSpeaking] = useState(false);
  const generate = () => {
    const typedIngredients = ingredientsText.split(',').map(item => item.trim()).filter(Boolean);
    const ingredients = typedIngredients.length ? typedIngredients : scans.data?.[0]?.ingredients ?? [];
    createGuide.mutate({ data: { dish, ingredients, allergies: profile.data?.allergies ?? [] } }, { onSuccess: result => { setGuide(result); setActiveStep(0); } });
  };
  const toggleVoice = () => {
    if (!guide || !('speechSynthesis' in window)) { setSpeaking(false); return; }
    if (speaking) { window.speechSynthesis.cancel(); setSpeaking(false); }
    else { const utterance = new SpeechSynthesisUtterance(guide.voiceScript || guide.steps[activeStep]); utterance.onend = () => setSpeaking(false); setSpeaking(true); window.speechSynthesis.speak(utterance); }
  };
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  return <>
    <PageHeading eyebrow="YOUR CALM IN-KITCHEN COMPANION" title="Let’s make something good." description="A clear, steady guide for what you’re already craving." />
    <div className="chef-layout">
      <div className="panel chef-prompt">
        <div className="chef-stamp"><CookingPot size={23} /></div><div className="eyebrow">A RECIPE, YOUR WAY</div><h2>What sounds<br /><em>good today?</em></h2><p>Tell your kitchen companion what you’d like to cook. We’ll make the steps easy to follow.</p>
        <label className="field-label" htmlFor="chef-dish">Dish or idea</label><input id="chef-dish" className="text-input" value={dish} onChange={e => setDish(e.target.value)} placeholder="e.g. lemony chickpea bowls" maxLength={120} data-testid="input-chef-dish" />
        <label className="field-label" htmlFor="chef-ingredients">Ingredients you have</label><input id="chef-ingredients" className="text-input" value={ingredientsText} onChange={e => setIngredientsText(e.target.value)} placeholder="Comma-separated ingredients" data-testid="input-chef-ingredients" />
        {scans.data?.[0] && <button className="text-button scan-ingredients-button" onClick={() => { setDish(scans.data?.[0]?.dishName ?? dish); setIngredientsText(scans.data?.[0]?.ingredients.join(', ') ?? ''); }} data-testid="button-use-latest-scan">Use latest scan: {scans.data[0].dishName}</button>}
        <div className="suggestions-label">A few ideas to begin</div><div className="suggestions">{['Herby lentil soup', 'Crispy tofu bowls', 'Lemon salmon'].map(item => <button key={item} onClick={() => setDish(item)} data-testid={`button-suggest-${item.toLowerCase().replaceAll(' ', '-')}`}>{item} <Plus size={13} /></button>)}</div>
        <button className="button button-primary full-button" onClick={generate} disabled={!dish.trim() || createGuide.isPending} data-testid="button-create-guide"><Sparkles size={16} />{createGuide.isPending ? 'Gathering the steps…' : 'Build my cooking guide'}<ArrowRight size={15} /></button>{createGuide.isError && <div className="inline-error">Your guide didn’t come together. Please try once more.</div>}<div className="chef-allergy-tip"><HeartPulse size={15} /><span>{profile.data?.allergies?.length ? `Your allergy notes are included: ${profile.data.allergies.join(', ')}` : 'Set your allergies in your profile to personalize recipe warnings.'}</span></div>
      </div>
      {guide ? <div className="panel guide-panel"><div className="guide-header"><div><div className="eyebrow">YOUR COOKING GUIDE</div><h2>{guide.dish}</h2><div className="guide-meta"><span><Clock3 size={14} /> {guide.prepMinutes} min prep</span><span><Flame size={14} /> {guide.cookMinutes} min cook</span><span><Utensils size={14} /> Serves {guide.servings}</span></div></div><button className={`voice-button ${speaking ? 'is-speaking' : ''}`} onClick={toggleVoice} data-testid="button-voice-playback"><AudioLines size={17} />{speaking ? 'Stop voice' : 'Listen'}</button></div>
        {guide.allergyWarnings.length > 0 && <div className="allergy-warning"><AlertTriangle size={16} /><div><strong>Allergy note</strong><span>{guide.allergyWarnings.join(' · ')}</span></div></div>}
        <div className="steps-heading"><span className="mini-heading">COOKING, ONE STEP AT A TIME</span><span>{activeStep + 1} / {guide.steps.length}</span></div><div className="step-progress">{guide.steps.map((_, i) => <i key={`step-${i}`} className={i <= activeStep ? 'done' : ''} />)}</div>
        <div className="active-step"><span className="step-number">{String(activeStep + 1).padStart(2, '0')}</span><div><span className="eyebrow">STEP {activeStep + 1}</span><p>{guide.steps[activeStep]}</p></div></div>
        <div className="step-controls"><button className="button button-outline" onClick={() => { setActiveStep(Math.max(activeStep - 1, 0)); window.speechSynthesis?.cancel(); setSpeaking(false); }} disabled={activeStep === 0} data-testid="button-previous-step">Previous</button><button className="button button-primary" onClick={() => { setActiveStep(Math.min(activeStep + 1, guide.steps.length - 1)); window.speechSynthesis?.cancel(); setSpeaking(false); }} disabled={activeStep === guide.steps.length - 1} data-testid="button-next-step">Next step <ArrowRight size={15} /></button></div>
        <div className="guide-extras"><details><summary>Ingredient substitutions <ChevronDown size={15} /></summary><ul>{guide.substitutions.map((item, i) => <li key={`${i}-${item}`}>{item}</li>)}</ul></details><details><summary>Allergy & ingredient notes <ChevronDown size={15} /></summary><ul>{guide.allergyWarnings.length ? guide.allergyWarnings.map((item, i) => <li key={`${i}-${item}`}>{item}</li>) : <li>No warnings returned. Always verify ingredient packaging for your needs.</li>}</ul></details></div>
      </div> : <div className="panel chef-empty"><div className="chef-art"><div className="plate-art"><span /><span /><span /><span /></div><i className="steam steam-one" /><i className="steam steam-two" /></div><span className="eyebrow">FROM IDEA TO TABLE</span><h3>A gentler way<br />to get dinner going.</h3><p>Your guide will include approachable steps, thoughtful substitutions, and allergy notes.</p><div className="empty-benefits"><span><Check size={14} /> Step-by-step pacing</span><span><Check size={14} /> Optional voice playback</span><span><Check size={14} /> Allergy-aware guidance</span></div>{scans.data?.length ? <div className="chef-recent">Inspired by your latest scan: <strong>{scans.data[0].dishName}</strong></div> : null}</div>}
    </div>
  </>;
}

function PlannerPage() {
  const qc = useQueryClient();
  const plan = useGetMealPlan();
  const profile = useGetProfile();
  const generatePlan = useGenerateMealPlan();
  const toggleMeal = useUpdateMealCompletion();
  const toggleGrocery = useUpdateGroceryItem();
  const [dayIndex, setDayIndex] = useState(0);
  const currentPlan = plan.data;
  const selectedDay = currentPlan?.days[Math.min(dayIndex, Math.max((currentPlan?.days.length ?? 1) - 1, 0))];
  const regenerate = () => generatePlan.mutate({ data: { weekOf: currentPlan?.weekOf ?? null } }, { onSuccess: () => { void qc.invalidateQueries({ queryKey: getGetMealPlanQueryKey() }); void qc.invalidateQueries({ queryKey: getGetDashboardQueryKey() }); } });
  const updateMeal = (id: string, completed: boolean) => toggleMeal.mutate({ mealId: id, data: { completed } }, { onSuccess: () => { void qc.invalidateQueries({ queryKey: getGetMealPlanQueryKey() }); void qc.invalidateQueries({ queryKey: getGetDashboardQueryKey() }); } });
  const updateGrocery = (id: string, checked: boolean) => toggleGrocery.mutate({ itemId: id, data: { checked } }, { onSuccess: () => void qc.invalidateQueries({ queryKey: getGetMealPlanQueryKey() }) });
  const [groceryFilter, setGroceryFilter] = useState('All');
  const groceryCategories = ['All', ...new Set(currentPlan?.groceryList.map(item => item.category) ?? [])];
  const groceryItems = useMemo(() => (currentPlan?.groceryList ?? []).filter(item => groceryFilter === 'All' || item.category === groceryFilter), [currentPlan?.groceryList, groceryFilter]);
  if (plan.isLoading) return <LoadingCards />;
  if (plan.isError) return <ErrorNotice retry={() => void plan.refetch()} />;
  return <>
    <PageHeading eyebrow="MAKE SPACE FOR GOOD FOOD" title="A week with a little more ease." description="A flexible plan, shaped around your goals and the things you love." action={<button className="button button-primary" onClick={regenerate} disabled={generatePlan.isPending} data-testid="button-generate-plan"><Sparkles size={16} />{generatePlan.isPending ? 'Putting it together…' : 'Refresh this week'}</button>} />
    {generatePlan.isError && <div className="inline-error">We couldn’t refresh your plan. Please try again.</div>}
    {!currentPlan || currentPlan.days.length === 0 ? <div className="panel empty-plan"><div className="plan-empty-icon"><ShoppingBasket size={25} /></div><h2>Your week is a blank page.</h2><p>Build a meal plan with your saved preferences{profile.data ? ` and ${pretty(profile.data.goal)} goal` : ''} in mind.</p><button className="button button-primary" onClick={regenerate} disabled={generatePlan.isPending} data-testid="button-build-plan"><Sparkles size={16} /> Create my weekly plan</button></div> : <>
      <div className="week-summary"><div className="week-copy"><span className="eyebrow">WEEK OF {new Date(`${currentPlan.weekOf}T12:00:00`).toLocaleDateString('en', { month: 'long', day: 'numeric' }).toUpperCase()}</span><h2>Room for good things.</h2><p>{profile.data ? `${pretty(profile.data.goal)}-minded ideas with a daily target of ${profile.data.calorieTarget.toLocaleString()} kcal.` : 'A flexible rhythm of breakfast, lunch, and dinner.'}</p></div><div className="week-stat"><span>PLAN PROGRESS</span><strong>{currentPlan.days.reduce((sum, day) => sum + day.meals.filter(meal => meal.completed).length, 0)}<small> / {currentPlan.days.reduce((sum, day) => sum + day.meals.length, 0)} meals</small></strong><div className="week-meter"><i style={{ width: `${Math.round(currentPlan.days.reduce((sum, day) => sum + day.meals.filter(meal => meal.completed).length, 0) / Math.max(currentPlan.days.reduce((sum, day) => sum + day.meals.length, 0), 1) * 100)}%` }} /></div></div><div className="week-decoration"><div /><div /><div /></div></div>
      <div className="day-strip" role="tablist" aria-label="Select a day">{currentPlan.days.map((day, index) => <button role="tab" aria-selected={index === dayIndex} className={dayIndex === index ? 'selected' : ''} onClick={() => setDayIndex(index)} key={day.date} data-testid={`tab-plan-day-${index}`}><span>{day.label}</span><strong>{new Date(`${day.date}T12:00:00`).getDate()}</strong><i>{day.meals.every(meal => meal.completed) && day.meals.length ? <Check size={12} /> : '·'}</i></button>)}</div>
      <div className="planner-columns"><section className="panel day-meals"><div className="panel-heading"><div><div className="eyebrow">YOUR DAY, YOUR PACE</div><h3>{selectedDay?.label ?? 'Meals'}</h3></div><span className="count-label">{selectedDay?.meals.length ?? 0} meals</span></div>{selectedDay?.meals.map(meal => <div className={`planned-meal ${meal.completed ? 'meal-complete' : ''}`} key={meal.id} data-testid={`card-meal-${meal.id}`}><button className={`meal-check ${meal.completed ? 'checked' : ''}`} aria-label={`${meal.completed ? 'Mark incomplete' : 'Mark complete'}: ${meal.name}`} onClick={() => updateMeal(meal.id, !meal.completed)} data-testid={`button-complete-meal-${meal.id}`}>{meal.completed && <Check size={14} />}</button><div className="meal-info"><span className="meal-slot">{meal.slot}</span><strong>{meal.name}</strong><div className="meal-tags">{meal.tags.map(tag => <span key={tag}>{tag}</span>)}</div></div><div className="meal-nutrition"><strong>{meal.calories}<small> kcal</small></strong><span>{meal.protein}g protein</span></div></div>)}{!selectedDay?.meals.length && <p className="empty-day">A free spot in the plan. Add something that feels right.</p>}<div className="day-total"><span>PLANNED FOR TODAY</span><strong>{selectedDay?.meals.reduce((sum, meal) => sum + meal.calories, 0).toLocaleString() ?? 0} <small>kcal</small></strong></div></section>
        <section className="panel grocery-panel"><div className="panel-heading"><div><div className="eyebrow">A LITTLE PREP GOES FAR</div><h3>Grocery list</h3></div><span className="grocery-count">{currentPlan.groceryList.filter(g => g.checked).length}/{currentPlan.groceryList.length}</span></div><div className="grocery-filters">{groceryCategories.slice(0, 4).map(category => <button key={category} className={groceryFilter === category ? 'active' : ''} onClick={() => setGroceryFilter(category)} data-testid={`filter-grocery-${category.toLowerCase()}`}>{pretty(category)}</button>)}</div><div className="grocery-items">{groceryItems.map(item => <label className={`grocery-item ${item.checked ? 'item-checked' : ''}`} key={item.id} data-testid={`item-grocery-${item.id}`}><input type="checkbox" checked={item.checked} onChange={e => updateGrocery(item.id, e.target.checked)} data-testid={`checkbox-grocery-${item.id}`} /><span className="custom-check">{item.checked && <Check size={12} />}</span><span className="grocery-name">{item.name}<small>{pretty(item.category)}</small></span><span className="grocery-qty">{item.quantity}</span></label>)}</div><div className="grocery-foot"><ShoppingBasket size={15} /><span>Good ingredients, ready when you are.</span></div></section></div>
    </>}
  </>;
}

function ProfilePage() {
  const qc = useQueryClient();
  const profile = useGetProfile();
  const save = useSaveProfile();
  const [calories, setCalories] = useState('');
  const [goal, setGoal] = useState<NutritionProfile['goal']>('balanced');
  const [allergyInput, setAllergyInput] = useState('');
  const [allergies, setAllergies] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [initialized, setInitialized] = useState(false);
  useEffect(() => {
    if (profile.data && !initialized) { setCalories(String(profile.data.calorieTarget)); setGoal(profile.data.goal); setAllergies(profile.data.allergies); setNotes(profile.data.dietaryNotes); setInitialized(true); }
  }, [profile.data, initialized]);
  const addAllergy = () => { const value = allergyInput.trim(); if (value && !allergies.some(item => item.toLowerCase() === value.toLowerCase())) setAllergies([...allergies, value]); setAllergyInput(''); };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate({ data: { calorieTarget: Number(calories), goal, allergies, dietaryNotes: notes } }, { onSuccess: () => void qc.invalidateQueries({ queryKey: getGetProfileQueryKey() }) });
  };
  if (profile.isLoading) return <LoadingCards />;
  if (profile.isError) return <ErrorNotice retry={() => void profile.refetch()} />;
  return <>
    <PageHeading eyebrow="MADE PERSONAL" title="Your food, your way." description="A few thoughtful details help make every insight feel more like yours." />
    <div className="profile-layout"><form className="panel profile-form" onSubmit={submit}>
      <div className="profile-section"><div className="profile-section-icon"><Gauge size={18} /></div><div className="profile-section-main"><h3>Your daily compass</h3><p>A flexible target, not a rulebook.</p><label className="field-label" htmlFor="calorie-target">Daily calorie target</label><div className="calorie-input"><input type="number" id="calorie-target" min="800" max="6000" value={calories} onChange={e => setCalories(e.target.value)} required data-testid="input-calorie-target" /><span>kcal / day</span></div><span className="field-hint">A useful estimate can vary with your needs and activity.</span></div></div>
      <div className="profile-divider" />
      <div className="profile-section"><div className="profile-section-icon"><HeartPulse size={18} /></div><div className="profile-section-main"><h3>What matters to you?</h3><p>Choose a direction that feels right right now.</p><div className="goal-options">{([{ value: 'balanced', label: 'Balanced', desc: 'A little of everything', icon: Leaf }, { value: 'vegan', label: 'Plant-forward', desc: 'Vegan choices', icon: Apple }, { value: 'muscle_gain', label: 'Strength', desc: 'Support muscle gain', icon: Activity }, { value: 'weight_loss', label: 'Lighter', desc: 'Weight management', icon: ArrowDownRight }, { value: 'low_carb', label: 'Lower carb', desc: 'Fewer refined carbs', icon: Wheat }, { value: 'keto', label: 'Keto', desc: 'Very low carb', icon: Flame }] as const).map(item => <button type="button" className={`goal-option ${goal === item.value ? 'selected' : ''}`} onClick={() => setGoal(item.value)} key={item.value} aria-pressed={goal === item.value} data-testid={`button-goal-${item.value}`}><item.icon size={17} /><strong>{item.label}</strong><span>{item.desc}</span>{goal === item.value && <Check size={14} className="goal-check" />}</button>)}</div></div></div>
      <div className="profile-divider" />
      <div className="profile-section"><div className="profile-section-icon amber"><AlertTriangle size={18} /></div><div className="profile-section-main"><h3>Allergies & sensitivities</h3><p>We'll surface notes when recipes are created.</p><div className="allergy-add"><input value={allergyInput} onChange={e => setAllergyInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addAllergy(); } }} placeholder="Add an allergy or sensitivity" aria-label="Add allergy" data-testid="input-allergy" /><button type="button" onClick={addAllergy} disabled={!allergyInput.trim()} className="button button-outline" data-testid="button-add-allergy"><Plus size={15} /> Add</button></div><div className="allergy-chips">{allergies.map(item => <span key={item}>{item}<button type="button" onClick={() => setAllergies(allergies.filter(x => x !== item))} aria-label={`Remove ${item}`} data-testid={`button-remove-allergy-${item.toLowerCase().replaceAll(' ', '-')}`}><X size={13} /></button></span>)}</div></div></div>
      <div className="profile-divider" />
      <div className="profile-section"><div className="profile-section-icon"><MoreHorizontal size={18} /></div><div className="profile-section-main"><h3>Notes for your kitchen</h3><p>Preferences, ingredients to skip, or anything else.</p><textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3} maxLength={500} placeholder="I love quick lunches, go easy on the spice…" data-testid="input-dietary-notes" /><div className="notes-count">{notes.length}/500</div></div></div>
      <div className="profile-actions"><span className="save-status">{save.isSuccess && <><CheckCircle2 size={15} /> Preferences saved</>}{save.isError && <span className="inline-error">Couldn’t save. Try again.</span>}</span><button type="submit" className="button button-primary" disabled={save.isPending || !calories} data-testid="button-save-profile">{save.isPending ? 'Saving…' : 'Save preferences'} <ArrowRight size={15} /></button></div>
    </form><aside className="profile-aside"><div className="panel preference-card"><div className="preference-art"><div className="preference-orbit"><span /><span /><span /></div><HeartPulse size={20} /></div><span className="eyebrow">A NOTE ON NUTRITION</span><h3>Good guidance<br />leaves room to be human.</h3><p>Food Verse offers estimates and helpful context—not a medical plan. Your needs are uniquely yours.</p><div className="preference-rule" /><Link href="/" className="subtle-link" data-testid="link-back-overview">Back to your overview <ArrowRight size={14} /></Link></div><div className="privacy-note"><ShieldCheck size={17} /><div><strong>Your choices stay yours.</strong><p>Use these preferences to shape the suggestions you see.</p></div></div></aside></div>
  </>;
}

function Router() {
  return <RoutedErrorBoundary><AppShell><Switch>
    <Route path="/" component={Dashboard} />
    <Route path="/scanner" component={ScannerPage} />
    <Route path="/hygiene" component={HygienePage} />
    <Route path="/chef" component={ChefPage} />
    <Route path="/planner" component={PlannerPage} />
    <Route path="/profile" component={ProfilePage} />
    <Route component={NotFound} />
  </Switch></AppShell></RoutedErrorBoundary>;
}
function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}
function App() {
  return <QueryClientProvider client={queryClient}><TooltipProvider><WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Router /></WouterRouter><Toaster /></TooltipProvider></QueryClientProvider>;
}
export default App;
