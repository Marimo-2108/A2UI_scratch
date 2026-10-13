import { createComponentImplementation } from '@a2ui/react/v0_9';
import { statCardApi } from './statCardApi';

const TREND = {
  up: { color: '#1a7f37', arrow: '▲' },
  down: { color: '#cf222e', arrow: '▼' },
  flat: { color: '#6e7781', arrow: '■' },
} as const;

/**
 * Implementation half of StatCard: how it LOOKS. The agent never sees this file.
 * `props` is already resolved by the library: a {path: "/x"} binding arrives as the
 * current string, and updates re-render this component automatically.
 */
export const StatCard = createComponentImplementation(statCardApi, ({ props }) => {
  const trend = TREND[props.trend ?? 'flat'];
  return (
    <div
      style={{
        border: '1px solid #8886',
        borderRadius: 10,
        padding: '10px 14px',
        minWidth: 140,
        background: '#8881',
      }}
    >
      <div style={{ fontSize: '.8rem', opacity: 0.7 }}>{props.label}</div>
      <div style={{ fontSize: '1.7rem', fontWeight: 700, lineHeight: 1.2 }}>{props.value}</div>
      {props.change ? (
        <div style={{ fontSize: '.85rem', color: trend.color }}>
          {trend.arrow} {props.change}
        </div>
      ) : null}
    </div>
  );
});
