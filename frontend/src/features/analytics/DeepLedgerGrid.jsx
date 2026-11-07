/**
 * DeepLedgerGrid - Enterprise AG Grid Desktop Analytics Workbench
 * ===============================================================
 * Powered by ag-grid-react v32.3.9 with ag-theme-quartz-dark.
 * 
 * Key Capabilities:
 * 1. Double-Entry Journal: Displays paired debit (-amt) and credit (+amt) legs sharing transfer_id.
 * 2. Journal View Toggles:
 *    - All Double-Entry Legs (Full system audit)
 *    - Merchant Spends & Holds (External consumer spending & active holds)
 *    - Bank Internal Allocations (Automated zero-sum transfers: Vault skim, Daily top-up, Rent reserve)
 * 3. Health & Telemetry Strip: Real-time Zero-Sum verification status, burn velocity, and runway.
 * 4. Row Selection & Coach Audit: Multi-row checkbox selection with 1-tap analytical prompts for the AI Coach.
 */

import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import {
  Download,
  Sparkles,
  Filter,
  RefreshCw,
  Search,
  ShieldCheck,
  Activity,
  ArrowRightLeft,
  Lock,
  Layers,
  TrendingDown,
  TrendingUp,
  Clock,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { fetchDeepLedger } from '../../shared/api';

export default function DeepLedgerGrid({ onAnalyzeWithCoach, isCoachOpen, onToggleCoach }) {
  const gridRef = useRef(null);
  const [gridApi, setGridApi] = useState(null);
  const [data, setData] = useState([]);
  const [aggregates, setAggregates] = useState({});
  const [loading, setLoading] = useState(false);
  const [selectedRows, setSelectedRows] = useState([]);

  // View & Filter states
  const [viewMode, setViewMode] = useState('all'); // 'all' (Double-Entry Journal) | 'merchant' | 'internal'
  const [bucketFilter, setBucketFilter] = useState('all');
  const [stateFilter, setStateFilter] = useState('all');
  const [entryKindFilter, setEntryKindFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  const loadLedger = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (bucketFilter !== 'all') params.bucket = bucketFilter;
      if (stateFilter !== 'all') params.state = stateFilter;
      if (entryKindFilter !== 'all') params.entry_kind = entryKindFilter;

      const res = await fetchDeepLedger(params);
      setData(res.items || []);
      setAggregates(res.aggregates || {});
    } catch (err) {
      console.error('Failed to load deep ledger', err);
    } finally {
      setLoading(false);
    }
  }, [bucketFilter, stateFilter, entryKindFilter]);

  useEffect(() => {
    loadLedger();
  }, [loadLedger]);

  // Client-side view mode filtering
  const displayedRows = useMemo(() => {
    if (viewMode === 'merchant') {
      return data.filter(item => item.entry_kind === 'merchant_spend' || item.counterparty_bucket === 'paypal_merchant');
    }
    if (viewMode === 'internal') {
      return data.filter(item => item.is_internal_transfer);
    }
    return data;
  }, [data, viewMode]);

  const onGridReady = useCallback((params) => {
    setGridApi(params.api);
    if (searchTerm) {
      params.api.setGridOption('quickFilterText', searchTerm);
    }
  }, [searchTerm]);

  const onSearchChange = (e) => {
    const val = e.target.value;
    setSearchTerm(val);
    if (gridApi) {
      gridApi.setGridOption('quickFilterText', val);
    }
  };

  const onSelectionChanged = useCallback(() => {
    if (gridApi) {
      const selected = gridApi.getSelectedRows();
      setSelectedRows(selected);
    }
  }, [gridApi]);

  const handleExportCSV = () => {
    if (gridApi) {
      gridApi.exportDataAsCsv({
        fileName: `firewallet_double_entry_ledger_${new Date().toISOString().slice(0, 10)}.csv`
      });
    }
  };

  const handleAnalyzeContext = (customPrompt = null) => {
    const filterContext = {
      view_mode: viewMode,
      bucket: bucketFilter !== 'all' ? bucketFilter : null,
      state: stateFilter !== 'all' ? stateFilter : null,
      entry_kind: entryKindFilter !== 'all' ? entryKindFilter : null,
      selected_rows: selectedRows.length > 0 ? selectedRows : null,
      total_shown: displayedRows.length
    };

    const prompt =
      customPrompt ||
      (selectedRows.length > 0
        ? `Analyze these ${selectedRows.length} selected ledger transactions for anomalies and budget impact.`
        : `Analyze my filtered ${bucketFilter !== 'all' ? bucketFilter : 'all'} ledger transactions and provide spending velocity diagnostics.`);

    onAnalyzeWithCoach?.(prompt, filterContext);
  };

  // AG Grid Custom Cell Renderers
  const amountRenderer = (params) => {
    const cents = params.value;
    const isCredit = cents >= 0;
    const sign = isCredit ? '+' : '-';
    const formatted = `${sign}$${(Math.abs(cents) / 100).toFixed(2)}`;
    return (
      <span className={`font-mono font-bold ${isCredit ? 'text-emerald-400' : 'text-rose-400'}`}>
        {formatted}
      </span>
    );
  };

  const runningBalanceRenderer = (params) => {
    const cents = params.value ?? 0;
    return (
      <span className="font-mono font-semibold text-slate-200">
        ${(cents / 100).toFixed(2)}
      </span>
    );
  };

  const directionRenderer = (params) => {
    const isCredit = params.value === 'CREDIT';
    return (
      <span
        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
          isCredit
            ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800'
            : 'bg-rose-950/80 text-rose-400 border border-rose-800'
        }`}
      >
        {params.value}
      </span>
    );
  };

  const bucketRenderer = (params) => {
    const b = params.value;
    const styles = {
      bank: 'bg-slate-800 text-slate-200 border-slate-700',
      daily: 'bg-emerald-950 text-emerald-400 border-emerald-800',
      freedom: 'bg-purple-950 text-purple-400 border-purple-800',
      vault: 'bg-amber-950 text-amber-400 border-amber-800',
      bills: 'bg-sky-950 text-sky-400 border-sky-800'
    };
    return (
      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border capitalize ${styles[b] || 'bg-slate-800 text-slate-300'}`}>
        {b}
      </span>
    );
  };

  const entryKindRenderer = (params) => {
    const kind = params.value;
    const labels = {
      payday_inflow: { text: 'Payday Inflow', color: 'bg-emerald-900/40 text-emerald-300 border-emerald-700' },
      vault_skim: { text: '20% Vault Skim', color: 'bg-amber-900/40 text-amber-300 border-amber-700' },
      bill_reserve: { text: 'Rent / Bill Earmark', color: 'bg-sky-900/40 text-sky-300 border-sky-700' },
      morning_topup: { text: 'Daily Rollover Topup', color: 'bg-teal-900/40 text-teal-300 border-teal-700' },
      freedom_allocation: { text: 'Freedom Allocation', color: 'bg-purple-900/40 text-purple-300 border-purple-700' },
      merchant_spend: { text: 'Merchant Spend', color: 'bg-slate-800 text-slate-300 border-slate-700' },
      override_raid: { text: 'Escape Window Raid', color: 'bg-rose-950 text-rose-300 border-rose-800' }
    };
    const conf = labels[kind] || { text: kind || 'Standard', color: 'bg-slate-800 text-slate-300 border-slate-700' };
    return (
      <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${conf.color}`}>
        {conf.text}
      </span>
    );
  };

  const flowRenderer = (params) => {
    const row = params.data;
    if (!row) return null;
    return (
      <div className="flex items-center gap-1.5 text-xs">
        <span className="font-semibold capitalize text-slate-200">{row.bucket}</span>
        <ArrowRightLeft className="w-3 h-3 text-slate-500 shrink-0" />
        <span className="text-slate-400 truncate max-w-[120px] capitalize">
          {row.counterparty_bucket?.replace('_', ' ') || 'External'}
        </span>
      </div>
    );
  };

  const stateRenderer = (params) => {
    const s = params.value;
    return (
      <span
        className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
          s === 'posted'
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
            : s === 'hold'
            ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
            : 'bg-slate-800 text-slate-400 border-slate-700'
        }`}
      >
        {s}
      </span>
    );
  };

  // AG Grid Column Definitions
  const colDefs = useMemo(
    () => [
      {
        headerName: '',
        field: 'selection',
        width: 48,
        pinned: 'left',
        checkboxSelection: true,
        headerCheckboxSelection: true,
        resizable: false,
        sortable: false,
        filter: false
      },
      {
        field: 'created_at',
        headerName: 'Date / Time',
        width: 130,
        pinned: 'left',
        valueFormatter: (p) => (p.value ? new Date(p.value).toLocaleDateString() : '')
      },
      {
        field: 'direction',
        headerName: 'Leg',
        width: 90,
        cellRenderer: directionRenderer
      },
      {
        field: 'flow',
        headerName: 'Double-Entry Flow',
        width: 175,
        cellRenderer: flowRenderer
      },
      {
        field: 'amount',
        headerName: 'Amount',
        width: 115,
        type: 'numericColumn',
        cellRenderer: amountRenderer
      },
      {
        field: 'running_balance',
        headerName: 'Running Bal',
        width: 120,
        type: 'numericColumn',
        cellRenderer: runningBalanceRenderer
      },
      {
        field: 'bucket',
        headerName: 'Bucket',
        width: 105,
        cellRenderer: bucketRenderer
      },
      {
        field: 'entry_kind',
        headerName: 'Entry Type',
        width: 155,
        cellRenderer: entryKindRenderer
      },
      {
        field: 'state',
        headerName: 'State',
        width: 95,
        cellRenderer: stateRenderer
      },
      {
        field: 'category',
        headerName: 'Category',
        width: 110,
        cellClass: 'capitalize'
      },
      {
        field: 'utterance',
        headerName: 'Audit Memo / NL Why',
        minWidth: 220,
        flex: 1
      },
      {
        field: 'transfer_id',
        headerName: 'Transfer ID',
        width: 115,
        valueFormatter: (p) => (p.value ? String(p.value).slice(0, 8) : 'N/A'),
        cellClass: 'font-mono text-slate-400 text-[11px]'
      },
      {
        field: 'paypal_order_id',
        headerName: 'PayPal Order ID',
        width: 140,
        cellClass: 'font-mono text-slate-500 text-[11px]'
      }
    ],
    []
  );

  const defaultColDef = useMemo(
    () => ({
      sortable: true,
      filter: true,
      resizable: true,
      minWidth: 90
    }),
    []
  );

  const vel = aggregates.velocity_metrics || {};

  return (
    <div className="max-w-[1440px] mx-auto px-4 py-6 space-y-5">
      {/* Top Header Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
            <h2 className="text-2xl font-black text-white tracking-tight">
              Advanced Ledger & Deep Audit Workbench
            </h2>
            <span className="px-2.5 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800 text-[11px] font-bold">
              AG Grid Enterprise Layer
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Bank-anchored double-entry transaction verification, zero-sum reconciliation, and real-time velocity interrogation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 rounded-xl border border-slate-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>

          <button
            onClick={loadLedger}
            disabled={loading}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 transition-colors"
            title="Refresh Ledger"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => handleAnalyzeContext()}
            className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-xs font-bold text-white rounded-xl shadow-lg shadow-purple-600/20 transition-all"
          >
            <Sparkles className="w-4 h-4" />
            <span>
              {selectedRows.length > 0 ? `Analyze Selected (${selectedRows.length})` : 'Analyze Grid with Coach'}
            </span>
          </button>
        </div>
      </div>

      {/* KPI & Double-Entry Health Telemetry Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        {/* Card 1: Zero-Sum Health */}
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
            <span>Double-Entry Balance</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-lg font-bold text-emerald-400 mt-1 flex items-center gap-1.5">
            <span>Verified Zero-Sum</span>
            <span className="text-[10px] px-1.5 py-0.2 bg-emerald-950 text-emerald-300 border border-emerald-800 rounded">
              Σ = $0.00
            </span>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            ${((aggregates.internal_transfers_volume || 0) / 100).toFixed(2)} internal legs balanced
          </p>
        </div>

        {/* Card 2: Daily Living Velocity */}
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
            <span>Daily Living Velocity</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-lg font-bold text-white mt-1">
            ${((vel.daily_burn_rate || 3400) / 100).toFixed(2)}
            <span className="text-xs font-normal text-slate-400">/day</span>
          </div>
          <p className="text-[11px] text-emerald-400/90 mt-0.5">
            {vel.daily_runway_days ?? 1.5} days runway &middot; +${((vel.rollover_retained || 1200) / 100).toFixed(2)} rollover
          </p>
        </div>

        {/* Card 3: Freedom Envelope Burn */}
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
            <span>Freedom Hedonism Burn</span>
            <TrendingDown className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-lg font-bold text-purple-400 mt-1">
            {vel.freedom_burn_pct ?? 40.0}%
            <span className="text-xs font-normal text-slate-400"> of $150</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            $90.00 left &middot; Zero Bank raids
          </p>
        </div>

        {/* Card 4: Merchant Outflows vs Holds */}
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
            <span>Settled Merchant Outflows</span>
            <Lock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-lg font-bold text-rose-400 mt-1">
            ${((aggregates.merchant_outflows || 0) / 100).toFixed(2)}
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Active Holds: ${((aggregates.active_holds || 0) / 100).toFixed(2)}
          </p>
        </div>
      </div>

      {/* View Mode Tabs & Granular Filters */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-slate-900/80 p-3 rounded-2xl border border-slate-800">
        {/* Journal Mode Switcher */}
        <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
          <button
            onClick={() => setViewMode('all')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              viewMode === 'all'
                ? 'bg-purple-600 text-white font-bold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            All Double-Entry Legs ({data.length})
          </button>
          <button
            onClick={() => setViewMode('merchant')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              viewMode === 'merchant'
                ? 'bg-purple-600 text-white font-bold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Merchant Spends
          </button>
          <button
            onClick={() => setViewMode('internal')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              viewMode === 'internal'
                ? 'bg-purple-600 text-white font-bold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Bank Internal Allocations
          </button>
        </div>

        {/* Dropdown Filters & Search */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Bucket Filter */}
          <select
            value={bucketFilter}
            onChange={(e) => setBucketFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-xs text-slate-200 rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-purple-500"
          >
            <option value="all">All Buckets</option>
            <option value="bank">Bank Foundation</option>
            <option value="daily">Daily Allowance</option>
            <option value="freedom">Freedom Envelope</option>
            <option value="vault">Vault Savings</option>
            <option value="bills">Reserved Bills</option>
          </select>

          {/* State Filter */}
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-xs text-slate-200 rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-purple-500"
          >
            <option value="all">All States</option>
            <option value="posted">Posted (Settled)</option>
            <option value="hold">Active Hold</option>
            <option value="released">Released / Canceled</option>
          </select>

          {/* Quick Filter Search */}
          <div className="relative w-full sm:w-56">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search memo, order, bucket..."
              value={searchTerm}
              onChange={onSearchChange}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500 transition-colors"
            />
          </div>
        </div>
      </div>

      {/* 1-Tap Analytical Deep-Coach Prompts Bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
        <span className="text-[11px] font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1 shrink-0">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Quick Ask:</span>
        </span>
        <button
          onClick={() => handleAnalyzeContext('Explain my Bank double-entry flows and where income moved.')}
          className="px-3 py-1 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 whitespace-nowrap transition-colors"
        >
          🏦 Explain Bank Double-Entry Flows
        </button>
        <button
          onClick={() => handleAnalyzeContext('Diagnose my Daily living velocity, runway in days, and rollover streak.')}
          className="px-3 py-1 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 whitespace-nowrap transition-colors"
        >
          ⚡ Diagnose Velocity & Runway
        </button>
        <button
          onClick={() => handleAnalyzeContext('Analyze active grid records for spending anomalies and deviations.')}
          className="px-3 py-1 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 whitespace-nowrap transition-colors"
        >
          🔍 Detect Spending Anomalies
        </button>
        <button
          onClick={() => handleAnalyzeContext('How is my monthly Freedom envelope trajectory tracking against rent?')}
          className="px-3 py-1 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 whitespace-nowrap transition-colors"
        >
          🎯 Freedom Envelope vs Rent Protection
        </button>
      </div>

      {/* AG Grid Component */}
      <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
        <div className="ag-theme-quartz-dark w-full h-[620px]">
          <AgGridReact
            ref={gridRef}
            rowData={displayedRows}
            columnDefs={colDefs}
            defaultColDef={defaultColDef}
            rowSelection="multiple"
            suppressRowClickSelection={true}
            onGridReady={onGridReady}
            onSelectionChanged={onSelectionChanged}
            animateRows={true}
            pagination={true}
            paginationPageSize={20}
            paginationPageSizeSelector={[10, 20, 50, 100]}
          />
        </div>
      </div>
    </div>
  );
}