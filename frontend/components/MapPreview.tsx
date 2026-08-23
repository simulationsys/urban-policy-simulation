"use client";
import React from "react";
import { MapContainer, TileLayer, Marker, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

// Fix leaflet default icon issue with webpack/nextjs
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const MapPreview = () => {
  // New Delhi coordinates
  const position: [number, number] = [28.6139, 77.2090]; 
  
  // A mock route for the polyline animation
  const route: [number, number][] = [
    [28.6139, 77.2090],
    [28.6150, 77.2100],
    [28.6200, 77.2150],
    [28.6250, 77.2250],
    [28.6300, 77.2200],
  ];

  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      <MapContainer 
        center={position} 
        zoom={13} 
        zoomControl={true}
        scrollWheelZoom={false}
        doubleClickZoom={true}
        dragging={true}
        touchZoom={true}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"
          attribution='&copy; OpenStreetMap contributors'
        />
        <Polyline 
          positions={route} 
          color="var(--color-primary)" 
          weight={4} 
        />
        {/* Animated moving dot on the route (simulating a car/agent) */}
        <Marker position={route[0]} />
      </MapContainer>
      
      {/* Overlay to give it a simulated dashboard feel */}
      <div className="absolute inset-0 z-[400] pointer-events-none" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0) 60%, var(--color-background) 100%)" }}></div>
    </div>
  );
};

export default MapPreview;
