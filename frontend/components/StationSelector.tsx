"use client";

/**
 * Station selector component with searchable dropdown
 * Uses pre-computed available stations list
 */

import { useState, useEffect, useRef, useMemo } from "react";
import type { StationSummary } from "@/types";

interface StationSelectorProps {
  stations: StationSummary[];
  selectedStation: StationSummary | null;
  onSelect: (station: StationSummary) => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
}

export default function StationSelector({
  stations,
  selectedStation,
  onSelect,
  isLoading = false,
  placeholder = "Select a station...",
  className = "",
}: StationSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Filter stations based on search query
  const filteredStations = useMemo(() => {
    if (!searchQuery.trim()) {
      return stations;
    }
    const query = searchQuery.toLowerCase();
    return stations.filter((station) =>
      station.name.toLowerCase().includes(query)
    );
  }, [stations, searchQuery]);

  // Reset highlighted index when filtered stations change
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [filteredStations]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setSearchQuery("");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const highlightedElement = listRef.current.children[highlightedIndex] as HTMLElement;
      if (highlightedElement) {
        highlightedElement.scrollIntoView({ block: "nearest" });
      }
    }
  }, [highlightedIndex]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) {
      if (e.key === "Enter" || e.key === "ArrowDown") {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setHighlightedIndex((prev) =>
          prev < filteredStations.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : 0));
        break;
      case "Enter":
        e.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < filteredStations.length) {
          handleSelect(filteredStations[highlightedIndex]);
        }
        break;
      case "Escape":
        e.preventDefault();
        setIsOpen(false);
        setSearchQuery("");
        inputRef.current?.blur();
        break;
    }
  };

  const handleSelect = (station: StationSummary) => {
    onSelect(station);
    setIsOpen(false);
    setSearchQuery("");
  };

  const displayValue = isOpen
    ? searchQuery
    : selectedStation?.name || "";

  return (
    <div ref={dropdownRef} className={`relative ${className}`}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={displayValue}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isLoading}
          className="w-full px-4 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
        />
        <div className="absolute right-3 top-2.5 pointer-events-none">
          {isLoading ? (
            <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
          ) : (
            <svg
              className={`h-5 w-5 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          )}
        </div>
      </div>

      {/* Dropdown */}
      {isOpen && !isLoading && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-80 overflow-hidden">
          {filteredStations.length > 0 ? (
            <>
              <div className="px-3 py-2 text-xs text-gray-500 border-b border-gray-200 bg-gray-50">
                {filteredStations.length} station{filteredStations.length !== 1 ? "s" : ""} available
              </div>
              <ul ref={listRef} className="overflow-y-auto max-h-64">
                {filteredStations.map((station, index) => (
                  <li key={station.eva}>
                    <button
                      onClick={() => handleSelect(station)}
                      className={`w-full text-left px-4 py-3 hover:bg-blue-50 transition-colors ${
                        index === highlightedIndex ? "bg-blue-100" : ""
                      } ${selectedStation?.eva === station.eva ? "bg-blue-50 font-medium" : ""}`}
                    >
                      <div className="text-gray-900">{station.name}</div>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="px-4 py-3 text-center text-gray-500">
              No stations found for &quot;{searchQuery}&quot;
            </div>
          )}
        </div>
      )}
    </div>
  );
}
