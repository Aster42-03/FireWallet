import React from 'react';

/**
 * Lightweight, zero-dependency Markdown renderer for FireWallet Chat
 * Supports:
 * - Bold (**text** or __text__)
 * - Italic (*text* or _text_)
 * - Inline code (`code`)
 * - Headers (### Header, ## Header, # Header)
 * - Bullet lists (- item, * item, 1. item)
 * - Paragraphs and line breaks
 */
export function MarkdownRenderer({ content, className = '' }) {
  if (!content) return null;

  const lines = content.split('\n');
  const elements = [];
  let currentList = null;

  const renderInline = (text) => {
    // Regex matches inline code `code`, bold **text**, and italic *text*
    const parts = [];
    let remaining = text;
    let key = 0;

    while (remaining) {
      // Inline code
      const codeMatch = remaining.match(/^(.*?)`([^`]+)`(.*)$/s);
      // Bold **text**
      const boldMatch = remaining.match(/^(.*?)\*\*([^*]+)\*\*(.*)$/s);
      // Italic *text*
      const italicMatch = remaining.match(/^(.*?)\*([^*]+)\*(.*)$/s);

      // Find whichever occurs first
      const matches = [
        codeMatch ? { type: 'code', index: codeMatch[1].length, match: codeMatch } : null,
        boldMatch ? { type: 'bold', index: boldMatch[1].length, match: boldMatch } : null,
        italicMatch ? { type: 'italic', index: italicMatch[1].length, match: italicMatch } : null,
      ].filter(Boolean);

      if (matches.length === 0) {
        parts.push(remaining);
        break;
      }

      matches.sort((a, b) => a.index - b.index);
      const first = matches[0];
      const m = first.match;

      if (m[1]) {
        parts.push(m[1]);
      }

      if (first.type === 'code') {
        parts.push(
          <code key={key++} className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-purple-300 font-mono text-[11px]">
            {m[2]}
          </code>
        );
      } else if (first.type === 'bold') {
        parts.push(
          <strong key={key++} className="font-bold text-white">
            {m[2]}
          </strong>
        );
      } else if (first.type === 'italic') {
        parts.push(
          <em key={key++} className="italic text-slate-300">
            {m[2]}
          </em>
        );
      }

      remaining = m[3];
    }

    return parts;
  };

  lines.forEach((line, lineIdx) => {
    const trimmed = line.trim();

    // Check header
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h4 key={`h3-${lineIdx}`} className="text-xs font-bold text-purple-300 mt-2 mb-1 uppercase tracking-wider">
          {renderInline(trimmed.slice(4))}
        </h4>
      );
      return;
    }
    if (trimmed.startsWith('## ')) {
      elements.push(
        <h3 key={`h2-${lineIdx}`} className="text-sm font-extrabold text-white mt-2 mb-1">
          {renderInline(trimmed.slice(3))}
        </h3>
      );
      return;
    }
    if (trimmed.startsWith('# ')) {
      elements.push(
        <h2 key={`h1-${lineIdx}`} className="text-base font-black text-white mt-2.5 mb-1.5">
          {renderInline(trimmed.slice(2))}
        </h2>
      );
      return;
    }

    // Bullet points
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      elements.push(
        <li key={`li-${lineIdx}`} className="ml-3.5 list-disc text-slate-200 pl-1 leading-relaxed">
          {renderInline(trimmed.slice(2))}
        </li>
      );
      return;
    }

    // Numbered list e.g. "1. "
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (numMatch) {
      elements.push(
        <div key={`num-${lineIdx}`} className="flex items-start gap-1.5 ml-1 my-0.5">
          <span className="font-bold text-purple-400 text-xs shrink-0">{numMatch[1]}.</span>
          <span className="text-slate-200 leading-relaxed">{renderInline(numMatch[2])}</span>
        </div>
      );
      return;
    }

    // Blank lines
    if (!trimmed) {
      elements.push(<div key={`blank-${lineIdx}`} className="h-1.5" />);
      return;
    }

    // Normal paragraph
    elements.push(
      <p key={`p-${lineIdx}`} className="leading-relaxed">
        {renderInline(trimmed)}
      </p>
    );
  });

  return <div className={`space-y-1 ${className}`}>{elements}</div>;
}
