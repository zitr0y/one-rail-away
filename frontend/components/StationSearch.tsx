"use client";

/**
 * Station search component with autocomplete
 */

import { useState, useEffect, useRef } from "react";
import { apiClient } from "@/lib/api";
import type { SearchStationResult } from "@/types";

interface StationSearchProps {
  onStationSelect: (station: SearchStationResult) => void;
  placeholder?: string;
  className?: string;
}

export default function StationSearch({
  onStationSelect,
  placeholder = "Search or click a station on map...",
  className = "",
}: StationSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchStationResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const searchRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounced search
  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      setShowResults(false);
      return;
    }

    const timeoutId = setTimeout(async () => {
      setIsSearching(true);
      try {
        const response = await apiClient.searchStations(query, 20);
        setResults(response.stations);
        setShowResults(true);
        setSelectedIndex(-1);
      } catch (error) {
        console.error("Error searching stations:", error);
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300); // 300ms debounce

    return () => clearTimeout(timeoutId);
  }, [query]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        searchRef.current &&
        !searchRef.current.contains(event.target as Node)
      ) {
        setShowResults(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showResults || results.length === 0) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < results.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case "Enter":
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < results.length) {
          handleSelect(results[selectedIndex]);
        }
        break;
      case "Escape":
        setShowResults(false);
        inputRef.current?.blur();
        break;
    }
  };

  const handleSelect = (station: SearchStationResult) => {
    setQuery(station.name);
    setShowResults(false);
    onStationSelect(station);
    inputRef.current?.blur();
  };

  return (
    <div ref={searchRef} className={`relative ${className}`}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (results.length > 0) {
              setShowResults(true);
            }
          }}
          placeholder={placeholder}
          className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <svg
          className="absolute left-3 top-2.5 h-5 w-5 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        {isSearching && (
          <div className="absolute right-3 top-2.5">
            <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
          </div>
        )}
      </div>

      {/* Results dropdown */}
      {showResults && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-80 overflow-y-auto">
          {results.map((station, index) => (
            <button
              key={station.id}
              onClick={() => handleSelect(station)}
              className={`w-full text-left px-4 py-3 hover:bg-blue-50 transition-colors ${
                index === selectedIndex ? "bg-blue-100" : ""
              } ${index !== results.length - 1 ? "border-b border-gray-100" : ""}`}
            >
              <div className="font-medium text-gray-900">{station.name}</div>
              <div className="text-xs text-gray-500 mt-1">
                {station.lat.toFixed(4)}, {station.lon.toFixed(4)}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* No results message */}
      {showResults && query.length >= 2 && results.length === 0 && !isSearching && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg p-4 text-center text-gray-500">
          No stations found for &quot;{query}&quot;
        </div>
      )}
    </div>
  );
}
