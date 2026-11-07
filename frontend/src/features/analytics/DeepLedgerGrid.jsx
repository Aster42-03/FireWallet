import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Download, Sparkles, Filter, RefreshCw, Search } from 'lucide-react';
import { fetchDeepLedger } from '../../shared/api';

export default function DeepLedgerGrid({ onAnalyzeWithCoach }) {
  const [data, setData] = useState([]);
  const [aggregates, setAggregates] = useState({});
  const [loading, setLoading] = useState(false);
  const [bucketFilter, setBucketFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  const loadLedger = async () => {
    setLoading(true);
    try {
      const params = {};
      if (bucketFilter !== 'all') params.bucket = bucketFilter;
      const res = await fetchDeepLedger(params);
      setData(res.items || []);
      setAggregates(res.aggregates || {});
    } catch (err) {
      console.error('Failed to load deep ledger', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLedger();
  }, [bucketFilter]);

  const filteredData = useMemo(() => {
    return data.filter(item => {
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        item.utterance?.toLowerCase().includes(term) ||
        item.category?.toLowerCase().includes(term) ||
        item.bucket?.toLowerCase().includes(term) ||
        item.paypal_order_id?.toLowerCase().includes(term)
      );
    });
  }, [data, searchTerm]);

  const handleExportCSV = () => {
    const headers = ['ID', 'Date', 'Category', 'Bucket', 'Amount Cents', 'State', 'Utterance', 'PayPal Order ID'];
    const rows = filteredData.map(item => [
      item.id,
      item.created_at,
      item.category,
      item.bucket,
      item.amount,
      item.state,
      `"${(item.utterance || '').replace(/"/g, '""')}"`,
      item.paypal_order_id || ''
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `firewallet_audit_ledger_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
            <h2 className="text-2xl font-extrabold text-white tracking-tight">Advanced Ledger & Deep Audit Workbench</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Enterprise transaction verification, audit trails, and multi-period anomaly detection powered by AG Grid.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 rounded-xl border border-slate-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            <span>Export CSV</span>
          </button>
          <button
            onClick={() => onAnalyzeWithCoach?.({ bucket: bucketFilter, count: filteredData.length })}
            className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-xs font-bold text-white rounded-xl shadow-md transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            <span>Analyze Grid with Coach</span>
          </button>
        </div>
      </div>

      {/* Aggregate Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Total Debits</span>
          <div className="text-xl font-bold text-rose-400 mt-1">
            ${((aggregates.total_debits || 0) / 100).toFixed(2)}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Total Credits</span>
          <div className="text-xl font-bold text-emerald-400 mt-1">
            ${((aggregates.total_credits || 0) / 100).toFixed(2)}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Active Holds</span>
          <div className="text-xl font-bold text-amber-400 mt-1">
            ${((aggregates.active_holds || 0) / 100).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400 ml-1" />
          <select
            value={bucketFilter}
            onChange={(e) => setBucketFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none"
          >
            <option value="all">All Trinity Buckets</option>
            <option value="bank">Bank</option>
            <option value="daily">Daily</option>
            <option value="freedom">Freedom</option>
            <option value="vault">Vault</option>
            <option value="bills">Bills</option>
          </select>
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search utterance or order..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
          />
        </div>
      </div>

      {/* High-Performance Desktop Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Bucket</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">State</th>
                <th className="py-3 px-4">Utterance / Memo</th>
                <th className="py-3 px-4">PayPal Correlation ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredData.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    {loading ? 'Loading ledger records...' : 'No transaction records found.'}
                  </td>
                </tr>
              ) : (
                filteredData.map(item => (
                  <tr key={item.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4 text-slate-300">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-slate-200 font-sans font-medium capitalize">
                      {item.category}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-sans font-semibold ${
                        item.bucket === 'daily' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                        item.bucket === 'freedom' ? 'bg-purple-950 text-purple-400 border border-purple-800' :
                        item.bucket === 'vault' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                        item.bucket === 'bills' ? 'bg-sky-950 text-sky-400 border border-sky-800' :
                        'bg-slate-800 text-slate-300'
                      }`}>
                        {item.bucket}
                      </span>
                    </td>
                    <td className={`py-3 px-4 font-bold ${item.amount < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                      {item.amount < 0 ? '-' : '+'}${Math.abs(item.amount / 100).toFixed(2)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-sans ${
                        item.state === 'posted' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' :
                        item.state === 'hold' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' :
                        'bg-slate-800 text-slate-400'
                      }`}>
                        {item.state}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-300 font-sans truncate max-w-xs">
                      {item.utterance}
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px] truncate max-w-[140px]">
                      {item.paypal_order_id || 'N/A'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
