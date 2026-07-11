import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { destinationsGeoJSON, linesGeoJSON, type MaxTrains } from "../lib/geojson";
import { BUCKET_COLORS } from "../lib/colors";
import { baseLineOpacity, selectedLineFilter } from "../lib/highlight";
import { pickFeature } from "../lib/pickfeature";
import { veilTooltip, showVeilTooltip } from "../lib/coverage";
import { api } from "../lib/api";
import { dotRadiusExpression, clusterRadiusExpression, sortForClusterList, drawStarIcon } from "../lib/dots";
import type { ReachFile, Station } from "../lib/types";

const CLICK_LAYERS = ["reach-dots", "capital-stars", "all-stations"];

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
  onEmptyClick: () => void;
}

export default function MapView(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;

  useEffect(() => {
    const coveragePromise = api.getCoverage();
    const m = new maplibregl.Map({
      container: container.current!,
      style: "https://tiles.openfreemap.org/styles/positron",
      center: [8, 50],
      zoom: 4.5,
    });
    m.on("load", () => {
      m.addSource("all-stations", {
        type: "geojson",
        data: EMPTY as never,
        cluster: true,
        clusterRadius: 30,
        clusterMaxZoom: 7,
      });
      m.addSource("reach-lines", { type: "geojson", data: EMPTY as never });
      m.addSource("reach-dots", { type: "geojson", data: EMPTY as never });
      m.addSource("coverage", { type: "geojson", data: EMPTY as never });
      m.addSource("capitals", { type: "geojson", data: EMPTY as never });
      m.addLayer({
        id: "all-stations", type: "circle", source: "all-stations",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-radius": dotRadiusExpression() as never,
          "circle-color": "#9ca3af", "circle-opacity": 0.7,
        },
      });
      m.addLayer({
        id: "station-clusters", type: "circle", source: "all-stations",
        filter: ["has", "point_count"],
        paint: {
          "circle-radius": clusterRadiusExpression() as never,
          "circle-color": "#9ca3af", "circle-opacity": 0.6,
        },
      });
      m.addLayer({
        id: "station-cluster-count", type: "symbol", source: "all-stations",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-size": 11,
        },
        paint: { "text-color": "#ffffff" },
      });
      m.addLayer(
        {
          id: "coverage-veil",
          type: "fill",
          source: "coverage",
          paint: {
            "fill-color": "#6b7280",
            "fill-opacity": ["match", ["get", "tier"], "light", 0.08, 0.16] as never,
          },
        },
        "all-stations",
      );
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
      m.addImage("star-icon", drawStarIcon(30) as any, { pixelRatio: 2 });
      m.addLayer({
        id: "capital-stars", type: "symbol", source: "capitals",
        layout: {
          "icon-image": "star-icon",
          "icon-size": 0.5,
          "icon-allow-overlap": true,
        },
      });
      const clusterPopup = new maplibregl.Popup({ closeButton: true, closeOnClick: true });
      m.on("click", (e) => {
        // 1. Cluster click — highest priority
        const clusterHits = m.queryRenderedFeatures(e.point, { layers: ["station-clusters"] });
        if (clusterHits.length) {
          const clusterId = clusterHits[0].properties!.cluster_id as number;
          const src = m.getSource("all-stations") as maplibregl.GeoJSONSource;
          src.getClusterLeaves(clusterId, 25, 0).then((leaves) => {
            const members = leaves.map((f) => ({
              id: f.properties!.id as string,
              name: f.properties!.name as string,
              n_dest: (f.properties!.n_dest as number) || 0,
            }));
            const sorted = sortForClusterList(members);
            const container = document.createElement("div");
            container.className = "cluster-popup";
            const ul = document.createElement("ul");
            for (const s of sorted) {
              const li = document.createElement("li");
              const btn = document.createElement("button");
              btn.textContent = s.name;
              btn.addEventListener("click", () => {
                propsRef.current.onSelectOrigin(s.id);
                clusterPopup.remove();
              });
              li.appendChild(btn);
              ul.appendChild(li);
            }
            container.appendChild(ul);
            clusterPopup.setLngLat(e.lngLat).setDOMContent(container).addTo(m);
          });
          return;
        }

        // 2. pickFeature — reach-dots > capital-stars > all-stations
        const hits = m.queryRenderedFeatures(e.point, { layers: CLICK_LAYERS })
          .map((f) => ({ layer: f.layer.id, id: f.properties!.id as string }));
        const pick = pickFeature(hits);
        if (!pick) {
          propsRef.current.onEmptyClick();
          return;
        }
        if (pick.type === "dest") propsRef.current.onSelectDestination(pick.id);
        else propsRef.current.onSelectOrigin(pick.id);
      });
      for (const layer of ["all-stations", "reach-dots", "capital-stars", "station-clusters"]) {
        m.on("mouseenter", layer, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", layer, () => (m.getCanvas().style.cursor = ""));
      }
      const veilPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      m.on("mousemove", "coverage-veil", (e) => {
        const stationHits = m.queryRenderedFeatures(e.point, { layers: CLICK_LAYERS }).length;
        if (!showVeilTooltip(stationHits)) {
          veilPopup.remove();
          return;
        }
        const tier = e.features?.[0]?.properties?.tier;
        veilPopup.setLngLat(e.lngLat).setText(veilTooltip(tier)).addTo(m);
      });
      m.on("mouseleave", "coverage-veil", () => veilPopup.remove());
      map.current = m;
      coveragePromise
        .then((fc) =>
          (m.getSource("coverage") as maplibregl.GeoJSONSource).setData(fc as never),
        )
        .catch(() => {
          // Veil is decorative; a missing coverage.json (404) just means no veil.
        });
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

    const nonCapitals = stations.filter((s) => s.has_reach && !s.is_capital);
    (m.getSource("all-stations") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: nonCapitals.map((s) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name, n_dest: s.n_dest },
      })),
    });

    const capitalStations = stations.filter((s) => s.is_capital);
    (m.getSource("capitals") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: capitalStations.map((s) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name, n_dest: s.n_dest },
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
