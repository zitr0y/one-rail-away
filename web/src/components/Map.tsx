import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { destinationsGeoJSON, linesGeoJSON, type MaxTrains } from "../lib/geojson";
import { BUCKET_COLORS } from "../lib/colors";
import { baseLineOpacity, selectedLineFilter } from "../lib/highlight";
import { pickFeature } from "../lib/pickfeature";
import type { ReachFile, Station } from "../lib/types";

const CLICK_LAYERS = ["reach-dots", "all-stations"];

const EMPTY = { type: "FeatureCollection", features: [] } as const;
const bucketColor = ["to-color", ["at", ["get", "bucket"], ["literal", BUCKET_COLORS]]];

interface Props {
  stations: Station[];
  reach: ReachFile | null;
  maxTrains: MaxTrains;
  maxMinutes: number;
  selectedDest: string | null;
  onSelectOrigin: (id: string) => void;
  onSelectDestination: (id: string) => void;
}

export default function MapView(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;

  useEffect(() => {
    const m = new maplibregl.Map({
      container: container.current!,
      style: "https://tiles.openfreemap.org/styles/positron",
      center: [8, 50],
      zoom: 4.5,
    });
    m.on("load", () => {
      m.addSource("all-stations", { type: "geojson", data: EMPTY as never });
      m.addSource("reach-lines", { type: "geojson", data: EMPTY as never });
      m.addSource("reach-dots", { type: "geojson", data: EMPTY as never });
      m.addLayer({
        id: "all-stations", type: "circle", source: "all-stations",
        paint: { "circle-radius": 3, "circle-color": "#9ca3af", "circle-opacity": 0.7 },
      });
      m.addLayer({
        id: "reach-lines", type: "line", source: "reach-lines",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": bucketColor as never,
          "line-width": ["case", ["==", ["get", "trains"], 1], 2.5, 1.5] as never,
          "line-opacity": baseLineOpacity(false),
        },
      });
      m.addLayer({
        id: "reach-lines-selected", type: "line", source: "reach-lines",
        layout: { "line-cap": "round", "line-join": "round" },
        filter: selectedLineFilter(null) as never,
        paint: {
          "line-color": bucketColor as never,
          "line-width": 4,
          "line-opacity": 1,
        },
      });
      m.addLayer({
        id: "reach-dots", type: "circle", source: "reach-dots",
        paint: {
          "circle-radius": 5.5, "circle-color": bucketColor as never,
          "circle-stroke-width": 1, "circle-stroke-color": "#ffffff",
        },
      });
      m.on("click", (e) => {
        const hits = m.queryRenderedFeatures(e.point, { layers: CLICK_LAYERS })
          .map((f) => ({ layer: f.layer.id, id: f.properties!.id as string }));
        const pick = pickFeature(hits);
        if (!pick) return;
        if (pick.type === "dest") propsRef.current.onSelectDestination(pick.id);
        else propsRef.current.onSelectOrigin(pick.id);
      });
      for (const layer of ["all-stations", "reach-dots"]) {
        m.on("mouseenter", layer, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", layer, () => (m.getCanvas().style.cursor = ""));
      }
      map.current = m;
      syncData();
      syncHighlight();
    });
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function syncData() {
    const m = map.current;
    if (!m) return;
    const { stations, reach, maxTrains, maxMinutes } = propsRef.current;
    const byId = new Map(stations.map((s) => [s.id, s]));
    (m.getSource("all-stations") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: stations.filter((s) => s.has_reach).map((s) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name },
      })),
    });
    (m.getSource("reach-lines") as maplibregl.GeoJSONSource).setData(
      reach ? (linesGeoJSON(reach, byId, maxTrains, maxMinutes) as never) : (EMPTY as never));
    (m.getSource("reach-dots") as maplibregl.GeoJSONSource).setData(
      reach ? (destinationsGeoJSON(reach, byId, maxTrains, maxMinutes) as never) : (EMPTY as never));
    const origin = reach && byId.get(reach.origin);
    if (origin) m.easeTo({ center: [origin.lon, origin.lat], zoom: 5 });
  }

  useEffect(syncData, [props.stations, props.reach, props.maxTrains, props.maxMinutes]);

  function syncHighlight() {
    const m = map.current;
    if (!m) return;
    const { selectedDest } = propsRef.current;
    m.setFilter("reach-lines-selected", selectedLineFilter(selectedDest) as never);
    m.setPaintProperty("reach-lines", "line-opacity", baseLineOpacity(selectedDest !== null));
  }

  useEffect(syncHighlight, [props.selectedDest]);

  return <div ref={container} style={{ position: "absolute", inset: 0 }} />;
}
