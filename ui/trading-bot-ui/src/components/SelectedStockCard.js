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
    <div className="tw-bg-gradient-to-r tw-from-slate-800/80 tw-to-slate-900/80 tw-rounded-xl tw-p-5 tw-border tw-border-slate-700/50 hover:tw-border-cyan-500/50 tw-transition-all tw-duration-300 hover:tw-shadow-xl">
      <div className="tw-grid tw-grid-cols-12 tw-gap-4 tw-items-center">
        {/* Symbol & Type */}
        <div className="tw-col-span-3">
          <div className="tw-text-2xl tw-font-extrabold tw-text-white tw-mb-1">{stock.symbol}</div>
          <div className="tw-flex tw-items-center tw-gap-2">
            <span className={`tw-inline-block tw-px-3 tw-py-1 tw-rounded-md tw-text-xs tw-font-bold ${stock.option_type === "CE" ? 'tw-bg-green-600 tw-text-white' : 'tw-bg-red-600 tw-text-white'}`}>
              {stock.option_type || "N/A"}
            </span>
            <span className="tw-text-xs tw-text-slate-400">{stock.sector || "N/A"}</span>
          </div>
          <div className="tw-text-[10px] tw-text-slate-500 tw-mt-1">
            Exp: {stock.expiry_date}
          </div>
        </div>

        {/* Strike & LTP */}
        <div className="tw-col-span-3">
          <div className="tw-text-xs tw-text-slate-400 tw-uppercase tw-mb-1">Strike / LTP</div>
          <div className="tw-text-lg tw-font-bold tw-text-white">{formatCurrency(stock.strike_price || 0)}</div>
          <div className="tw-text-base tw-font-bold tw-text-cyan-400">{formatCurrency(ltp)}</div>
          <div className="tw-text-[10px] tw-text-slate-500 tw-mt-1">
            Score: <span className={score > 70 ? 'tw-text-emerald-400' : 'tw-text-amber-400'}>{score}/100</span>
          </div>
        </div>

        {/* Lot Info */}
        <div className="tw-col-span-2">
          <div className="tw-text-xs tw-text-slate-400 tw-uppercase tw-mb-1">Lot Size</div>
          <div className="tw-text-lg tw-font-bold tw-text-white">{lotSize}</div>
          <div className="tw-text-sm tw-text-slate-400">x {lotsToTrade} lots</div>
        </div>

        {/* Capital Required */}
        <div className="tw-col-span-2">
          <div className="tw-text-xs tw-text-slate-400 tw-uppercase tw-mb-1">Capital & Targets</div>
          <div className="tw-text-lg tw-font-extrabold tw-text-orange-400">{formatCurrency(capitalRequired)}</div>
          <div className="tw-flex tw-gap-2 tw-text-[10px] tw-mt-1">
            <span className="tw-text-rose-400">L: {stock.max_loss}</span>
            <span className="tw-text-emerald-400">T: {stock.target_profit}</span>
          </div>
        </div>

        {/* Status & AI Sentiment & Chart */}
        <div className="tw-col-span-2 tw-text-right tw-flex tw-flex-col tw-items-end">
          <span className={`tw-inline-block tw-px-3 tw-py-1.5 tw-rounded-lg tw-text-xs tw-font-bold ${stock.trade_status === "TRADED" ? 'tw-bg-green-600 tw-text-white' : stock.trade_status === "IN_POSITION" ? 'tw-bg-yellow-600 tw-text-white' : 'tw-bg-blue-600 tw-text-white'}`}> 
            {stock.trade_status || "SELECTED"}
          </span>
          <div className="tw-mt-1 tw-inline-flex tw-items-center tw-gap-1 tw-px-2 tw-py-0.5 tw-bg-blue-500/10 tw-border tw-border-blue-500/30 tw-rounded tw-text-[10px] tw-font-black tw-text-blue-400">
            🤖 AI Conviction: {stock.ai_confidence ? `${stock.ai_confidence}%` : "85% High"}
          </div>
          {onOpenChart && (
            <button
              onClick={() => onOpenChart(stock.symbol)}
              className="tw-mt-1.5 tw-px-2.5 tw-py-1 tw-bg-slate-800 hover:tw-bg-slate-700 tw-border tw-border-slate-700 tw-rounded tw-text-[11px] tw-font-semibold tw-text-cyan-400 tw-transition-colors"
            >
              📈 Live Chart
            </button>
          )}
        </div>

        {/* Reason Row */}
        {stock.selection_reason && (
          <div className="tw-col-span-12 tw-mt-2 tw-pt-2 tw-border-t tw-border-slate-700/30">
            <p className="tw-text-[11px] tw-text-slate-400 tw-italic">
              <span className="tw-font-semibold tw-text-slate-500">Analysis: </span>
              {stock.selection_reason}
            </p>
          </div>
        )}
      </div>
    </div>
  );
});

export default SelectedStockCard;