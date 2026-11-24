import React, { useState, useEffect, useRef } from 'react';
import { Search, MapPin, X, Loader2 } from 'lucide-react';
import { Stop } from '../types/api';
import { apiService } from '../services/api';

interface StopSearchInputProps {
  label: string;
  placeholder: string;
  selectedStop: Stop | null;
  coordinateText: string;
  placeName?: string;
  onSelectStop: (stop: Stop | null) => void;
  onClear: () => void;
  badgeColor?: string;
  dotColor?: string;
}

export const StopSearchInput: React.FC<StopSearchInputProps> = ({
  label,
  placeholder,
  selectedStop,
  coordinateText,
  placeName,
  onSelectStop,
  onClear,
  badgeColor = 'text-blue-600',
  dotColor = 'bg-blue-600',
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Stop[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Debounced stop search
  useEffect(() => {
    if (!query.trim() || selectedStop) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await apiService.searchStops(query, 8);
        setResults(res.stops);
        setIsOpen(true);
      } catch (err) {
        console.error('Stop search failed', err);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query, selectedStop]);

  const handleSelect = (stop: Stop) => {
    onSelectStop(stop);
    setQuery(stop.stop_name);
    setIsOpen(false);
  };

  const handleClear = () => {
    setQuery('');
    setResults([]);
    onClear();
  };

  const displayInputValue = selectedStop
    ? selectedStop.stop_name
    : placeName || coordinateText || query;

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="flex items-center justify-between mb-1">
        <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider flex items-center space-x-1.5">
          <span className={`w-2 h-2 rounded-full ${dotColor} inline-block`} />
          <span>{label}</span>
        </label>
        {selectedStop && (
          <span className="text-[10px] text-slate-400 font-mono bg-slate-100 px-1.5 py-0.2 rounded border border-slate-200">
            ID: {selectedStop.stop_id}
          </span>
        )}
      </div>

      <div className="relative flex items-center">
        <MapPin className={`absolute left-3 w-4 h-4 ${badgeColor}`} />

        <input
          type="text"
          value={displayInputValue}
          onChange={(e) => {
            if (selectedStop || coordinateText || placeName) {
              onClear();
            }
            setQuery(e.target.value);
          }}
          placeholder={placeholder}
          className="w-full pl-9 pr-8 py-2.5 text-sm bg-white border border-slate-200 hover:border-slate-300 rounded-xl shadow-xs focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors text-slate-800 placeholder:text-slate-400 font-medium"
        />

        {loading ? (
          <Loader2 className="absolute right-3 w-4 h-4 text-slate-400 animate-spin" />
        ) : selectedStop || coordinateText || placeName || query ? (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2.5 p-1 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
            title="Clear selection"
          >
            <X className="w-4 h-4" />
          </button>
        ) : (
          <Search className="absolute right-3 w-4 h-4 text-slate-400 pointer-events-none" />
        )}
      </div>

      {/* Coordinate mode badge with human-readable place resolution */}
      {!selectedStop && (placeName || coordinateText) && (
        <div className="mt-1 text-[11px] text-slate-500 flex items-center space-x-1.5 flex-wrap">
          <span className="font-medium text-emerald-800 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
            📍 {placeName || 'Selected Location'}
          </span>
          {coordinateText && (
            <span className="font-mono bg-slate-50 text-slate-600 px-1.5 py-0.5 rounded border border-slate-200 text-[10px]">
              [{coordinateText}]
            </span>
          )}
        </div>
      )}

      {/* Autocomplete Dropdown */}
      {isOpen && results.length > 0 && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-xl max-h-56 overflow-y-auto divide-y divide-slate-100">
          {results.map((stop) => (
            <button
              key={stop.stop_id}
              type="button"
              onClick={() => handleSelect(stop)}
              className="w-full text-left px-3.5 py-2.5 hover:bg-blue-50/60 transition-colors flex items-center justify-between group"
            >
              <div>
                <p className="text-sm font-semibold text-slate-800 group-hover:text-blue-700">
                  {stop.stop_name}
                </p>
                <p className="text-xs text-slate-400 font-mono">
                  Stop ID: {stop.stop_id} &bull; [{stop.lat.toFixed(4)}, {stop.lon.toFixed(4)}]
                </p>
              </div>
              <span className="text-xs text-blue-600 opacity-0 group-hover:opacity-100 font-medium transition-opacity">
                Select &rarr;
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
