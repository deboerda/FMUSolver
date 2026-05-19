import { useState, useMemo, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

// ─── Color palette (matched to 图一 sci-fi HUD style) ────────────────────────
const C = {
  bg:           '#020b18',
  panel:        '#030f22',
  panelMid:     '#041428',
  cyan:         '#00d4e8',
  cyanBright:   '#00f5ff',
  cyanA10:      'rgba(0,212,232,0.10)',
  cyanA15:      'rgba(0,212,232,0.15)',
  cyanA25:      'rgba(0,212,232,0.25)',
  cyanA40:      'rgba(0,212,232,0.40)',
  amber:        '#f5a623',
  amberA20:     'rgba(245,166,35,0.20)',
  purple:       '#b260d6',
  green:        '#00c853',
  red:          '#ef5350',
  white:        '#d8eef8',
  muted:        '#5fa8bc',
  dim:          '#234556',
  gridLine:     'rgba(0,212,232,0.12)',
  borderCyan:   '1px solid #00d4e8',
  headerBg:     'rgba(0,212,232,0.10)',
};

// ─── Monitoring parameter list ────────────────────────────────────────────────
const PARAMS = [
  { id: 'temp4',      code: 'Temp4',      name: '主机排气温度',           color: C.amber  },
  { id: 'zspeed4',    code: 'Z Speed4',   name: 'A排增压器转速',          color: C.cyan   },
  { id: 'zspeed82',   code: 'Z Speed82',  name: 'B排增压器转速',          color: C.purple },
  { id: 'aeqas12',    code: 'A Eqas12',   name: 'A列增压器供气温度',      color: C.cyan   },
  { id: 'beqas12',    code: 'B Eqas12',   name: 'B列增压器进后气温度',    color: C.cyan   },
  { id: 'astemp4',    code: 'As Temp4',   name: 'A排空冷器前空气温度',    color: C.cyan   },
  { id: 'betemp4',    code: 'Be Temp4',   name: 'A排空冷器后空气温度',    color: C.cyan   },
  { id: 'bepa4',      code: 'Be Pa4',     name: 'A排空冷器出口空气压力',  color: C.cyan   },
  { id: 'fuelrack4',  code: 'FuelRack4',  name: '油门',                   color: C.cyan   },
  { id: 'power4',     code: 'Power4',     name: '柴油机功率',             color: C.cyan   },
  { id: 'rspeed4',    code: 'R speed4',   name: '柴油机转速',             color: C.cyan   },
];

// ─── Chart data ───────────────────────────────────────────────────────────────
function generateChartData() {
  const pts: { t: number; temp4: number; zSpeed4: number; zSpeed82: number }[] = [];
  for (let i = 0; i <= 480; i++) {
    const t = 14.75 + (i / 480) * 6;
    pts.push({
      t: parseFloat(t.toFixed(3)),
      temp4:    parseFloat((Math.sin(t * 20.1) * 0.22 + Math.sin(t * 40.2) * 0.06 + Math.cos(t * 8.0) * 0.07).toFixed(4)),
      zSpeed4:  parseFloat((Math.sin(t * 23.3 + 0.7) * 0.27 + Math.sin(t * 46.6) * 0.05 + Math.cos(t * 10.0 + 1.0) * 0.05).toFixed(4)),
      zSpeed82: parseFloat((Math.sin(t * 18.8 + 2.0) * 0.20 + Math.sin(t * 37.6 + 1.5) * 0.08 + Math.cos(t * 7.5 + 0.8) * 0.06).toFixed(4)),
    });
  }
  return pts;
}

// ─── Sci-Fi Panel wrapper ─────────────────────────────────────────────────────
interface PanelProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  cornerSize?: number;
  noGlow?: boolean;
}
function SciFiPanel({ children, className = '', style = {}, cornerSize = 12, noGlow = false }: PanelProps) {
  const cp = (c: number) =>
    `polygon(${c}px 0%,calc(100% - ${c}px) 0%,100% ${c}px,100% calc(100% - ${c}px),calc(100% - ${c}px) 100%,${c}px 100%,0% calc(100% - ${c}px),0% ${c}px)`;
  return (
    <div
      className={className}
      style={{
        filter: noGlow ? undefined : 'drop-shadow(0 0 6px rgba(0,212,232,0.35))',
        ...style,
      }}
    >
      <div
        style={{
          height: '100%',
          clipPath: cp(cornerSize),
          border: C.borderCyan,
          background: C.panel,
          boxSizing: 'border-box',
          overflow: 'hidden',
        }}
      >
        {children}
      </div>
    </div>
  );
}

// ─── Panel section header ─────────────────────────────────────────────────────
function SectionHeader({ title }: { title: string }) {
  return (
    <div
      style={{
        background: C.headerBg,
        borderBottom: `1px solid ${C.cyanA40}`,
        borderLeft: `3px solid ${C.cyan}`,
        padding: '5px 10px',
        color: C.cyan,
        fontFamily: "'Rajdhani', 'Noto Sans SC', sans-serif",
        letterSpacing: '0.08em',
        fontSize: 13,
        fontWeight: 600,
      }}
    >
      {title}
    </div>
  );
}

// ─── Custom chart tooltip ─────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: 'rgba(2,11,24,0.97)',
        border: `1px solid ${C.cyan}`,
        padding: '8px 12px',
        boxShadow: `0 0 12px ${C.cyanA40}`,
        fontFamily: "'Share Tech Mono', monospace",
        fontSize: 12,
      }}
    >
      <p style={{ color: C.cyan, marginBottom: 4 }}>时间: {Number(label).toFixed(3)} s</p>
      {payload.map((entry: any, i: number) => {
        const nameMap: Record<string, string> = {
          temp4: '主机排气温度',
          zSpeed4: 'A排增压器转速',
          zSpeed82: 'B排增压器转速',
        };
        return (
          <p key={i} style={{ color: entry.stroke, margin: '2px 0' }}>
            {nameMap[entry.dataKey] ?? entry.dataKey}: {Number(entry.value).toFixed(4)}
          </p>
        );
      })}
    </div>
  );
}

// ─── SCI-FI button ────────────────────────────────────────────────────────────
function SciFiButton({
  children, onClick, color = C.cyan, filled = false, small = false,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  color?: string;
  filled?: boolean;
  small?: boolean;
}) {
  const [hov, setHov] = useState(false);
  const cp = 'polygon(6px 0%,calc(100% - 6px) 0%,100% 6px,100% calc(100% - 6px),calc(100% - 6px) 100%,6px 100%,0% calc(100% - 6px),0% 6px)';
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        clipPath: cp,
        border: 'none',
        background: filled
          ? hov ? color + 'cc' : color
          : hov ? `${color}33` : `${color}1a`,
        color: filled ? '#020b18' : color,
        fontFamily: "'Rajdhani','Noto Sans SC',sans-serif",
        fontWeight: 700,
        fontSize: small ? 11 : 13,
        letterSpacing: '0.06em',
        padding: small ? '4px 12px' : '7px 20px',
        cursor: 'pointer',
        outline: `1px solid ${color}`,
        outlineOffset: '-1px',
        transition: 'background 0.2s',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </button>
  );
}

// ─── SCI-FI checkbox ─────────────────────────────────────────────────────────
function SciFiCheckbox({
  checked, onChange, label,
}: { checked: boolean; onChange: () => void; label?: string }) {
  return (
    <label
      style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', userSelect: 'none' }}
      onClick={onChange}
    >
      <div
        style={{
          width: 13, height: 13, border: `1px solid ${checked ? C.cyan : C.dim}`,
          background: checked ? C.cyanA25 : 'transparent',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
          transition: 'all 0.15s',
          boxShadow: checked ? `0 0 4px ${C.cyanA40}` : 'none',
        }}
      >
        {checked && (
          <div style={{ width: 7, height: 7, background: C.cyan }} />
        )}
      </div>
      {label && (
        <span style={{ color: C.muted, fontSize: 12, fontFamily: "'Noto Sans SC',sans-serif" }}>
          {label}
        </span>
      )}
    </label>
  );
}

// ─── Y-axis label (vertical) ──────────────────────────────────────────────────
const YAxisLabel = ({ viewBox }: any) => {
  if (!viewBox) return null;
  const { x, y, height } = viewBox;
  return (
    <text
      x={x - 14}
      y={y + height / 2}
      textAnchor="middle"
      transform={`rotate(-90, ${x - 14}, ${y + height / 2})`}
      fill={C.muted}
      fontSize={11}
      fontFamily="'Noto Sans SC',sans-serif"
    >
      振幅修正值
    </text>
  );
};

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState(1);
  const [checkedParams, setCheckedParams] = useState<Set<string>>(
    new Set(['temp4', 'zspeed4', 'zspeed82'])
  );
  const [activeParam, setActiveParam] = useState('zspeed82');
  const [isRunning, setIsRunning] = useState(false);
  const [timeSpan, setTimeSpan] = useState('15');
  const [autoFollow, setAutoFollow] = useState(true);
  const [activeTableRow, setActiveTableRow] = useState(2);
  const [dataCount] = useState(1285);

  const chartData = useMemo(() => generateChartData(), []);

  const tabs = ['3#仿真数据', '4#仿真数据', '3#试验数据'];

  const toggleParam = useCallback((id: string) => {
    setCheckedParams(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const tableRows = [
    { id: 0, region: '4#仿真数据', tag: '主机排气温度', code: 'Temp4',    value: '0.0000', peak: '0.0000', color: C.amber  },
    { id: 1, region: '4#仿真数据', tag: 'A排增压器转速', code: 'Z_Speed4',  value: '0.0000', peak: '0.0000', color: C.cyan   },
    { id: 2, region: '4#仿真数据', tag: 'B排增压器转速', code: 'Z_Speed82', value: '0.0000', peak: '0.0000', color: C.purple },
  ];

  return (
    <div
      style={{
        height: '100vh',
        width: '100vw',
        display: 'flex',
        flexDirection: 'column',
        background: C.bg,
        overflow: 'hidden',
        fontFamily: "'Noto Sans SC', sans-serif",
        color: C.white,
        userSelect: 'none',
      }}
    >
      {/* ── TITLE BAR ─────────────────────────────────────────────────────── */}
      <div
        style={{
          height: 44,
          background: C.panelMid,
          borderBottom: `1px solid ${C.cyanA40}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 14px',
          flexShrink: 0,
        }}
      >
        {/* Left accent */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', gap: 3 }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{ width: 4, height: 22 - i * 5, background: C.cyan, opacity: 1 - i * 0.25 }} />
            ))}
          </div>
          <span
            style={{
              fontFamily: "'Rajdhani','Noto Sans SC',sans-serif",
              fontSize: 16,
              fontWeight: 700,
              color: C.cyanBright,
              letterSpacing: '0.1em',
              textShadow: `0 0 12px ${C.cyan}`,
            }}
          >
            柴油机实时监控与数据校验工具
          </span>
          <span
            style={{
              fontFamily: "'Share Tech Mono',monospace",
              fontSize: 12,
              color: C.amber,
              letterSpacing: '0.05em',
            }}
          >
            v3.4 专业版
          </span>
        </div>

        {/* Right: status + controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div
              style={{
                width: 7, height: 7, borderRadius: '50%',
                background: isRunning ? C.green : C.red,
                boxShadow: `0 0 6px ${isRunning ? C.green : C.red}`,
              }}
            />
            <span style={{ fontSize: 12, color: isRunning ? C.green : C.red, fontFamily: "'Share Tech Mono',monospace" }}>
              {isRunning ? '运行中' : '已停止'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {['─', '□', '?'].map((s, i) => (
              <button
                key={i}
                style={{
                  width: 24, height: 20, background: C.cyanA10, border: `1px solid ${C.cyanA25}`,
                  color: C.muted, fontSize: 11, cursor: 'pointer', display: 'flex',
                  alignItems: 'center', justifyContent: 'center',
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── MAIN CONTENT ROW ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', padding: '8px', gap: 8 }}>

        {/* ── LEFT SIDEBAR: 监测指标体系 ───────────────────────────────────── */}
        <SciFiPanel style={{ width: 210, flexShrink: 0, height: '100%' }} cornerSize={10}>
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Sidebar header */}
            <div
              style={{
                background: 'rgba(0,212,232,0.12)',
                borderBottom: `1px solid ${C.cyanA40}`,
                padding: '7px 10px',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <div style={{ width: 2, height: 16, background: C.cyan }} />
              <span
                style={{
                  color: C.cyanBright,
                  fontFamily: "'Rajdhani','Noto Sans SC',sans-serif",
                  fontSize: 13,
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                }}
              >
                监测指标体系
              </span>
            </div>

            {/* Tabs */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                borderBottom: `1px solid ${C.cyanA25}`,
                background: C.bg,
                padding: '4px 4px 0',
                gap: 2,
                flexShrink: 0,
              }}
            >
              {tabs.map((tab, i) => (
                <button
                  key={i}
                  onClick={() => setActiveTab(i)}
                  style={{
                    flex: 1,
                    padding: '4px 2px',
                    fontSize: 10,
                    fontFamily: "'Noto Sans SC',sans-serif",
                    background: activeTab === i ? C.cyanA25 : 'transparent',
                    border: 'none',
                    borderBottom: activeTab === i ? `2px solid ${C.cyan}` : '2px solid transparent',
                    color: activeTab === i ? C.cyanBright : C.dim,
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    letterSpacing: '0.02em',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {tab}
                </button>
              ))}
              <button
                style={{
                  width: 18, padding: '4px 2px', background: 'transparent', border: 'none',
                  color: C.muted, fontSize: 12, cursor: 'pointer',
                }}
              >
                ?
              </button>
              <button
                style={{
                  width: 18, padding: '4px 2px', background: 'transparent', border: 'none',
                  color: C.muted, fontSize: 12, cursor: 'pointer',
                }}
              >
                ?
              </button>
            </div>

            {/* Parameter list */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
              {PARAMS.map((p) => {
                const isActive = activeParam === p.id;
                const isChecked = checkedParams.has(p.id);
                return (
                  <div
                    key={p.id}
                    onClick={() => setActiveParam(p.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 7,
                      padding: '5px 8px',
                      cursor: 'pointer',
                      background: isActive ? 'rgba(0,180,220,0.22)' : 'transparent',
                      borderLeft: isActive ? `3px solid ${C.cyan}` : '3px solid transparent',
                      transition: 'background 0.15s',
                    }}
                  >
                    <div onClick={(e) => { e.stopPropagation(); toggleParam(p.id); }}>
                      <SciFiCheckbox checked={isChecked} onChange={() => toggleParam(p.id)} />
                    </div>
                    <div
                      style={{
                        width: 6, height: 6, borderRadius: '50%',
                        background: isChecked ? p.color : C.dim,
                        flexShrink: 0,
                        boxShadow: isChecked ? `0 0 5px ${p.color}` : 'none',
                      }}
                    />
                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 11,
                          color: isActive ? C.cyanBright : isChecked ? C.white : C.dim,
                          fontFamily: "'Share Tech Mono',monospace",
                          lineHeight: 1.2,
                        }}
                      >
                        {p.code}
                      </div>
                      <div
                        style={{
                          fontSize: 10,
                          color: isActive ? C.cyan : C.muted,
                          fontFamily: "'Noto Sans SC',sans-serif",
                          lineHeight: 1.2,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: 148,
                        }}
                      >
                        ({p.name})
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Sidebar footer stats */}
            <div
              style={{
                borderTop: `1px solid ${C.cyanA25}`,
                padding: '6px 10px',
                display: 'flex',
                justifyContent: 'space-between',
                background: C.bg,
              }}
            >
              <span style={{ fontSize: 10, color: C.dim }}>已选: {checkedParams.size} 项</span>
              <span style={{ fontSize: 10, color: C.dim }}>共 {PARAMS.length} 指标</span>
            </div>
          </div>
        </SciFiPanel>

        {/* ── RIGHT: Chart + Table ─────────────────────────────────────────── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, overflow: 'hidden', minWidth: 0 }}>

          {/* ── CHART PANEL ─────────────────────────────────────────────── */}
          <SciFiPanel style={{ flex: 3, minHeight: 0 }} cornerSize={12}>
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <SectionHeader title="曲线监控 · 振幅修正值" />

              {/* Legend row */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  gap: 16,
                  padding: '5px 16px',
                  borderBottom: `1px solid ${C.cyanA10}`,
                  flexShrink: 0,
                }}
              >
                {[
                  { label: '主机排气温度 (Temp4)',    color: C.amber  },
                  { label: 'A排增压器转速 (Z_Speed4)', color: C.cyan   },
                  { label: 'B排增压器转速 (Z_Speed82)', color: C.purple },
                ].map((leg) => (
                  <div key={leg.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <div
                      style={{
                        width: 22, height: 2, background: leg.color,
                        boxShadow: `0 0 4px ${leg.color}`,
                      }}
                    />
                    <span style={{ fontSize: 10, color: C.muted, fontFamily: "'Noto Sans SC',sans-serif" }}>
                      {leg.label}
                    </span>
                  </div>
                ))}
              </div>

              {/* Chart */}
              <div style={{ flex: 1, minHeight: 0, padding: '4px 4px 0 0' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={chartData}
                    margin={{ top: 10, right: 20, left: 56, bottom: 28 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={C.gridLine} />
                    <XAxis
                      dataKey="t"
                      type="number"
                      domain={[14.75, 20.75]}
                      tickCount={13}
                      tick={{ fill: C.muted, fontSize: 10, fontFamily: "'Share Tech Mono',monospace" }}
                      tickFormatter={(v) => Number(v).toFixed(2)}
                      stroke={C.cyanA40}
                      label={{
                        value: '时间 [s]',
                        position: 'insideBottom',
                        offset: -10,
                        fill: C.muted,
                        fontSize: 11,
                        fontFamily: "'Noto Sans SC',sans-serif",
                      }}
                    />
                    <YAxis
                      domain={[-0.4, 0.4]}
                      tickCount={9}
                      tick={{ fill: C.muted, fontSize: 10, fontFamily: "'Share Tech Mono',monospace" }}
                      tickFormatter={(v) => Number(v).toFixed(1)}
                      stroke={C.cyanA40}
                      label={<YAxisLabel />}
                    />
                    <ReferenceLine y={0} stroke={C.amber} strokeDasharray="5 3" strokeWidth={1} opacity={0.6} />
                    <Tooltip content={<CustomTooltip />} />
                    {checkedParams.has('temp4') && (
                      <Line
                        type="monotoneX"
                        dataKey="temp4"
                        stroke={C.amber}
                        dot={false}
                        strokeWidth={1.5}
                        isAnimationActive={false}
                        activeDot={{ r: 3, fill: C.amber }}
                      />
                    )}
                    {checkedParams.has('zspeed4') && (
                      <Line
                        type="monotoneX"
                        dataKey="zSpeed4"
                        stroke={C.cyan}
                        dot={false}
                        strokeWidth={1.5}
                        isAnimationActive={false}
                        activeDot={{ r: 3, fill: C.cyan }}
                      />
                    )}
                    {checkedParams.has('zspeed82') && (
                      <Line
                        type="monotoneX"
                        dataKey="zSpeed82"
                        stroke={C.purple}
                        dot={false}
                        strokeWidth={1.5}
                        isAnimationActive={false}
                        activeDot={{ r: 3, fill: C.purple }}
                      />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </SciFiPanel>

          {/* ── DATA TABLE ──────────────────────────────────────────────── */}
          <SciFiPanel style={{ flex: 2, minHeight: 0 }} cornerSize={10}>
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <SectionHeader title="监控数据记录" />

              {/* Table header */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1.6fr 1fr 1fr',
                  padding: '5px 12px',
                  borderBottom: `1px solid ${C.cyanA40}`,
                  background: 'rgba(0,212,232,0.06)',
                  flexShrink: 0,
                }}
              >
                {['区域', '标签名称', '当前数值', '峰值'].map((h) => (
                  <span
                    key={h}
                    style={{
                      fontSize: 11,
                      color: C.cyan,
                      fontFamily: "'Noto Sans SC',sans-serif",
                      letterSpacing: '0.05em',
                      fontWeight: 500,
                    }}
                  >
                    {h}
                  </span>
                ))}
              </div>

              {/* Table body */}
              <div style={{ flex: 1, overflowY: 'auto' }}>
                {tableRows.map((row) => {
                  const isActive = activeTableRow === row.id;
                  return (
                    <div
                      key={row.id}
                      onClick={() => setActiveTableRow(row.id)}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1.6fr 1fr 1fr',
                        padding: '7px 12px',
                        borderBottom: `1px solid ${C.cyanA10}`,
                        background: isActive ? 'rgba(0,180,220,0.18)' : 'transparent',
                        borderLeft: isActive ? `3px solid ${C.cyan}` : '3px solid transparent',
                        cursor: 'pointer',
                        transition: 'background 0.15s',
                        alignItems: 'center',
                      }}
                    >
                      {/* Region */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div
                          style={{
                            width: 5, height: 5, borderRadius: '50%',
                            background: row.color,
                            boxShadow: `0 0 4px ${row.color}`,
                          }}
                        />
                        <span
                          style={{
                            fontSize: 11,
                            color: isActive ? C.cyanBright : C.muted,
                            fontFamily: "'Noto Sans SC',sans-serif",
                          }}
                        >
                          {row.region}
                        </span>
                      </div>
                      {/* Tag */}
                      <span
                        style={{
                          fontSize: 11,
                          color: isActive ? C.white : C.muted,
                          fontFamily: "'Noto Sans SC',sans-serif",
                        }}
                      >
                        {row.tag}
                        <span
                          style={{
                            marginLeft: 5,
                            fontSize: 10,
                            color: row.color,
                            fontFamily: "'Share Tech Mono',monospace",
                          }}
                        >
                          ({row.code})
                        </span>
                      </span>
                      {/* Value */}
                      <span
                        style={{
                          fontSize: 12,
                          color: isActive ? C.cyanBright : C.white,
                          fontFamily: "'Share Tech Mono',monospace",
                          letterSpacing: '0.03em',
                        }}
                      >
                        {row.value}
                      </span>
                      {/* Peak */}
                      <span
                        style={{
                          fontSize: 12,
                          color: isActive ? C.amber : C.muted,
                          fontFamily: "'Share Tech Mono',monospace",
                          letterSpacing: '0.03em',
                        }}
                      >
                        {row.peak}
                      </span>
                    </div>
                  );
                })}

                {/* Empty rows filler */}
                {Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={`empty-${i}`}
                    style={{
                      padding: '6px 12px',
                      borderBottom: `1px solid rgba(0,212,232,0.04)`,
                      height: 30,
                    }}
                  />
                ))}
              </div>
            </div>
          </SciFiPanel>
        </div>
      </div>

      {/* ── BOTTOM CONTROLS ───────────────────────────────────────────────── */}
      <div
        style={{
          height: 52,
          flexShrink: 0,
          background: C.panelMid,
          borderTop: `1px solid ${C.cyanA40}`,
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          padding: '0 14px',
        }}
      >
        {/* Start/Stop */}
        <SciFiButton
          onClick={() => setIsRunning(v => !v)}
          color={isRunning ? C.red : C.green}
          filled
        >
          {isRunning ? '停止监控' : '启动监控'}
        </SciFiButton>

        {/* Divider */}
        <div style={{ width: 1, height: 30, background: C.cyanA25 }} />

        {/* Time span */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: C.muted }}>时间跨度：</span>
          <div style={{ position: 'relative' }}>
            <select
              value={timeSpan}
              onChange={(e) => setTimeSpan(e.target.value)}
              style={{
                background: C.cyanA10,
                border: `1px solid ${C.cyanA40}`,
                color: C.cyanBright,
                padding: '4px 24px 4px 10px',
                fontSize: 12,
                fontFamily: "'Share Tech Mono',monospace",
                appearance: 'none',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              {['5', '10', '15', '30', '60'].map(v => (
                <option key={v} value={v} style={{ background: C.panelMid }}>{v} 秒</option>
              ))}
            </select>
            <span
              style={{
                position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)',
                color: C.cyan, fontSize: 10, pointerEvents: 'none',
              }}
            >
              ▼
            </span>
          </div>
        </div>

        {/* Auto follow */}
        <SciFiCheckbox
          checked={autoFollow}
          onChange={() => setAutoFollow(v => !v)}
          label="自动跟踪视角"
        />

        {/* Divider */}
        <div style={{ width: 1, height: 30, background: C.cyanA25 }} />

        <SciFiButton color={C.red}>清空保存</SciFiButton>
        <SciFiButton color={C.cyan}>复位坐标</SciFiButton>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Quick stats */}
        <div style={{ display: 'flex', gap: 16 }}>
          {[
            { label: '采样频率', value: '500 Hz' },
            { label: '通道数',   value: '3 路' },
          ].map((stat) => (
            <div key={stat.label} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 9, color: C.dim, fontFamily: "'Noto Sans SC',sans-serif" }}>{stat.label}</div>
              <div style={{ fontSize: 12, color: C.cyan, fontFamily: "'Share Tech Mono',monospace" }}>{stat.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── STATUS BAR ────────────────────────────────────────────────────── */}
      <div
        style={{
          height: 24,
          flexShrink: 0,
          background: '#01070f',
          borderTop: `1px solid ${C.cyanA25}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 14px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              color: isRunning ? C.green : C.red,
              fontSize: 11,
              fontFamily: "'Share Tech Mono',monospace",
            }}
          >
            <div
              style={{
                width: 5, height: 5, borderRadius: '50%',
                background: isRunning ? C.green : C.red,
                boxShadow: `0 0 4px ${isRunning ? C.green : C.red}`,
              }}
            />
            {isRunning ? '运行中' : '停止'}
          </div>
          <span style={{ color: C.dim, fontSize: 11 }}>|</span>
          <span
            style={{
              color: C.muted, fontSize: 11,
              fontFamily: "'Share Tech Mono',monospace",
            }}
          >
            已存储 <span style={{ color: C.cyan }}>{dataCount.toLocaleString()}</span> 点数据
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: C.dim, fontSize: 10, fontFamily: "'Share Tech Mono',monospace" }}>
            当前标签页：{tabs[activeTab]}
          </span>
          <span style={{ color: C.dim, fontSize: 10, fontFamily: "'Share Tech Mono',monospace" }}>
            时间跨度：{timeSpan}秒
          </span>
          <span style={{ color: C.dim, fontSize: 10, fontFamily: "'Share Tech Mono',monospace" }}>
            就绪
          </span>
        </div>
      </div>
    </div>
  );
}
