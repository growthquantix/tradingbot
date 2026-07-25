import React, { memo } from 'react';

const formatCurrency = (amount) => {
  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(Math.abs(amount || 0));
  return `${amount < 0 ? '-' : ''}₹${formatted}`;
};

const SelectedStockCard = memo(({ stock, onOpenChart }) => {
  const lotsToTrade = stock.position_size_lots || 1;
  const lotSize = stock.lot_size || 0;
  const totalQty = lotsToTrade * lotSize;
  const ltp = stock.live_price || stock.premium || 0;
  const capitalRequired = ltp * totalQty;
  const score = stock.selection_score || 0;

  return (
    <div className="premium-glass-card tw-rounded-2xl tw-p-5 tw-border tw-border-slate-800/80 hover:tw-border-cyan-500/50 tw-transition-all tw-duration-300 hover:tw-shadow-2xl hover:tw-shadow-cyan-500/10">
      <div className="tw-grid tw-grid-cols-1 sm:tw-grid-cols-2 lg:tw-grid-cols-12 tw-gap-4 tw-items-center">
        {/* Symbol & Type (lg: 3 units) */}
        <div className="lg:tw-col-span-3">
          <div className="tw-flex tw-items-center tw-justify-between sm:tw-justify-start tw-gap-2">
            <span className="tw-text-2xl tw-font-black tw-text-white tw-tracking-tight">{stock.symbol}</span>
            <span className={`tw-px-3 tw-py-1 tw-rounded-lg tw-text-xs tw-font-black tw-uppercase ${
              stock.option_type === "CE" ? 'tw-bg-emerald-500/20 tw-text-emerald-400 tw-border tw-border-emerald-500/30' : 'tw-bg-rose-500/20 tw-text-rose-400 tw-border tw-border-rose-500/30'
            }`}>
              {stock.option_type || "N/A"}
            </span>
          </div>
          <div className="tw-flex tw-items-center tw-gap-2 tw-mt-1.5">
            <span className="tw-text-xs tw-text-slate-400 tw-font-semibold">{stock.sector || "N/A"}</span>
            <span className="tw-text-slate-700">•</span>
            <span className="tw-text-[11px] tw-text-slate-500 tw-font-mono">Exp: {stock.expiry_date || "Weekly"}</span>
          </div>
        </div>

        {/* Strike & LTP (lg: 3 units) */}
        <div className="lg:tw-col-span-3">
          <div className="tw-text-[10px] tw-text-slate-500 tw-uppercase tw-font-bold tw-tracking-wider tw-mb-0.5">Strike / LTP</div>
          <div className="tw-flex tw-items-baseline tw-gap-2">
            <span className="tw-text-lg tw-font-bold tw-text-white tw-font-mono">{formatCurrency(stock.strike_price || 0)}</span>
            <span className="tw-text-base tw-font-black tw-text-cyan-400 tw-font-mono">{formatCurrency(ltp)}</span>
          </div>
          <div className="tw-text-[10px] tw-text-slate-500 tw-mt-1">
            Signal Score: <span className={`tw-font-bold ${score > 70 ? 'tw-text-emerald-400' : 'tw-text-amber-400'}`}>{score}/100</span>
          </div>
        </div>

        {/* Lot Info (lg: 2 units) */}
        <div className="lg:tw-col-span-2">
          <div className="tw-text-[10px] tw-text-slate-500 tw-uppercase tw-font-bold tw-tracking-wider tw-mb-0.5">Position Lot</div>
          <div className="tw-text-lg tw-font-bold tw-text-slate-200 tw-font-mono">{lotSize} <span className="tw-text-xs tw-text-slate-500 font-normal">units</span></div>
          <div className="tw-text-xs tw-text-cyan-400 tw-font-semibold">{lotsToTrade} Lots ({totalQty} Total Qty)</div>
        </div>

        {/* Capital Required (lg: 2 units) */}
        <div className="lg:tw-col-span-2">
          <div className="tw-text-[10px] tw-text-slate-500 tw-uppercase tw-font-bold tw-tracking-wider tw-mb-0.5">Capital Required</div>
          <div className="tw-text-lg tw-font-black tw-text-amber-400 tw-font-mono">{formatCurrency(capitalRequired)}</div>
          <div className="tw-flex tw-gap-2 tw-text-[10px] tw-mt-1">
            <span className="tw-text-rose-400 tw-font-semibold">SL: {stock.max_loss || "2% Risk"}</span>
            <span className="tw-text-emerald-400 tw-font-semibold">TGT: {stock.target_profit || "Dynamic"}</span>
          </div>
        </div>

        {/* Status & AI Conviction & Chart (lg: 2 units) */}
        <div className="lg:tw-col-span-2 sm:tw-text-right tw-flex tw-flex-col sm:tw-items-end tw-gap-1.5">
          <span className={`tw-inline-block tw-px-3 tw-py-1 tw-rounded-lg tw-text-xs tw-font-black tw-uppercase ${
            stock.trade_status === "TRADED" ? 'tw-bg-emerald-500/20 tw-text-emerald-400 tw-border tw-border-emerald-500/40' : 
            stock.trade_status === "IN_POSITION" ? 'tw-bg-amber-500/20 tw-text-amber-400 tw-border tw-border-amber-500/40' : 
            'tw-bg-cyan-500/20 tw-text-cyan-400 tw-border tw-border-cyan-500/40'
          }`}> 
            {stock.trade_status || "READY"}
          </span>

          <div className="tw-inline-flex tw-items-center tw-gap-1 tw-px-2.5 tw-py-1 tw-bg-cyan-500/10 tw-border tw-border-cyan-500/30 tw-rounded-lg tw-text-[10px] tw-font-black tw-text-cyan-300">
            🤖 AI Conviction: {stock.ai_confidence ? `${stock.ai_confidence}%` : "85% High"}
          </div>

          {onOpenChart && (
            <button
              onClick={() => onOpenChart(stock.symbol)}
              className="tw-w-full sm:tw-w-auto tw-px-3 tw-py-1.5 tw-bg-slate-800 hover:tw-bg-slate-700 tw-border tw-border-slate-700 hover:tw-border-cyan-500/50 tw-rounded-xl tw-text-xs tw-font-bold tw-text-cyan-400 tw-transition-all tw-flex tw-items-center tw-justify-center tw-gap-1"
            >
              <span>📈 Live Chart</span>
            </button>
          )}
        </div>

        {/* Reason Row */}
        {stock.selection_reason && (
          <div className="lg:tw-col-span-12 tw-mt-2 tw-pt-3 tw-border-t tw-border-slate-800/60">
            <p className="tw-text-xs tw-text-slate-400 tw-italic">
              <span className="tw-font-bold tw-text-cyan-400/80 tw-not-italic">AI Signal Thesis: </span>
              {stock.selection_reason}
            </p>
          </div>
        )}
      </div>
    </div>
  );
});

export default SelectedStockCard;