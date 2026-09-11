import { useState } from "react";
import { IconActivity, IconImage } from "@/components/ui/Icon";

interface EquipmentTag {
  id: string;
  label: string;
  type: string;
  spec: string;
  coords: string;
  score: number;
}

const TAGS: EquipmentTag[] = [
  {
    id: "FV-302",
    label: "Control Valve FV-302",
    type: "Flow Control / Fail Closed",
    spec: "ASME B16.34 Class 300 / Pneumatic Diaphragm Actuator",
    coords: "ymin: 412, xmin: 120, ymax: 480, xmax: 210",
    score: 0.892,
  },
  {
    id: "PT-101",
    label: "Transmitter PT-101",
    type: "Pressure Sensor [0-600 PSI]",
    spec: "4-20mA HART / Piezoresistive / Ex d IIC T4",
    coords: "ymin: 240, xmin: 310, ymax: 310, xmax: 390",
    score: 0.941,
  },
  {
    id: "P-101A",
    label: "Pump P-101A",
    type: "API 610 Centrifugal Pump",
    spec: "180 m3/h @ 85m Head / 75 kW 3-Phase Induction Motor",
    coords: "ymin: 150, xmin: 520, ymax: 290, xmax: 680",
    score: 0.915,
  },
  {
    id: "R-301",
    label: "Reactor R-301",
    type: "Hydrotreater Vessel",
    spec: "ASME BPVC Sec VIII Div 1 / MAWP: 450 PSI @ 350°C",
    coords: "ymin: 380, xmin: 650, ymax: 560, xmax: 820",
    score: 0.884,
  },
];

export function VisualEvidenceScene() {
  const [selectedTag, setSelectedTag] = useState<EquipmentTag>(TAGS[0]);

  return (
    <section id="pid-vision" className="py-20 px-4 sm:px-8 max-w-6xl mx-auto border-b border-surface-border">
      <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/40 bg-indigo-500/10 px-3 py-0.5 text-xs font-mono text-indigo-400">
          <IconImage className="h-3.5 w-3.5" />
          <span>ZERO-OCR CAD &amp; P&amp;ID VISUAL REASONING</span>
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold text-ink-1">
          Spatial P&amp;ID Grounding with ColModernVBERT
        </h2>
        <p className="text-xs sm:text-sm text-ink-2 leading-relaxed">
          OCR destroys spatial context in complex piping and instrumentation diagrams.
          CogniShift performs visual token late-interaction directly on engineering drawing rasters,
          locating tag bubbles and physical pipe interconnections without OCR degradation.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Interactive Schematic Diagram (SVG) */}
        <div className="lg:col-span-7 rounded-xl border border-surface-border bg-surface-1 p-4 shadow-xl relative overflow-hidden">
          <div className="flex items-center justify-between border-b border-surface-border/60 pb-2.5 mb-3 font-mono text-[11px] text-ink-3">
            <span className="text-brand font-bold">DWG: P-ID-04-B // SHEET 2 [REFINERY SECTION 4]</span>
            <span>SCALE: 1:50 CAD</span>
          </div>

          <svg
            viewBox="0 0 900 600"
            className="w-full h-auto rounded border border-surface-border/40 bg-black/60 select-none"
          >
            {/* Grid background */}
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />

            {/* Piping lines */}
            <path d="M 50 220 L 520 220" stroke="#384355" strokeWidth="3" fill="none" />
            <path d="M 680 220 L 800 220 L 800 380" stroke="#384355" strokeWidth="3" fill="none" />
            <path d="M 350 220 L 350 290" stroke="#384355" strokeWidth="2" strokeDasharray="4 2" fill="none" />
            <path d="M 165 220 L 165 420 L 735 420 L 735 380" stroke="#0891b2" strokeWidth="2" strokeDasharray="5 3" fill="none" />

            {/* Flow arrows */}
            <polygon points="260,216 270,220 260,224" fill="#384355" />
            <polygon points="740,216 750,220 740,224" fill="#384355" />

            {/* Equipment: Pump P-101A */}
            <g
              onClick={() => setSelectedTag(TAGS[2])}
              className="cursor-pointer transition-transform hover:scale-105"
            >
              <circle cx="600" cy="220" r="45" fill="#0d1117" stroke={selectedTag.id === "P-101A" ? "#34d399" : "#384355"} strokeWidth="2.5" />
              <polygon points="600,175 645,220 600,265" fill={selectedTag.id === "P-101A" ? "rgba(52,211,153,0.15)" : "transparent"} stroke={selectedTag.id === "P-101A" ? "#34d399" : "#384355"} strokeWidth="2" />
              <text x="600" y="225" textAnchor="middle" fill="#e6ebf1" fontFamily="monospace" fontSize="12" fontWeight="bold">P-101A</text>
            </g>

            {/* Equipment: Sensor PT-101 */}
            <g
              onClick={() => setSelectedTag(TAGS[1])}
              className="cursor-pointer transition-transform hover:scale-105"
            >
              <circle cx="350" cy="290" r="28" fill="#0d1117" stroke={selectedTag.id === "PT-101" ? "#22d3ee" : "#384355"} strokeWidth="2" />
              <line x1="322" y1="290" x2="378" y2="290" stroke="#384355" strokeWidth="1" />
              <text x="350" y="282" textAnchor="middle" fill="#e6ebf1" fontFamily="monospace" fontSize="10" fontWeight="bold">PT</text>
              <text x="350" y="303" textAnchor="middle" fill="#22d3ee" fontFamily="monospace" fontSize="10" fontWeight="bold">101</text>
            </g>

            {/* Equipment: Valve FV-302 */}
            <g
              onClick={() => setSelectedTag(TAGS[0])}
              className="cursor-pointer transition-transform hover:scale-105"
            >
              <polygon points="135,405 195,435 135,435 195,405" fill="#0d1117" stroke={selectedTag.id === "FV-302" ? "#818cf8" : "#384355"} strokeWidth="2" />
              <line x1="165" y1="420" x2="165" y2="390" stroke="#818cf8" strokeWidth="1.5" />
              <circle cx="165" cy="385" r="8" fill="#0d1117" stroke="#818cf8" strokeWidth="1.5" />
              <text x="165" y="455" textAnchor="middle" fill="#818cf8" fontFamily="monospace" fontSize="11" fontWeight="bold">FV-302</text>
            </g>

            {/* Equipment: Reactor R-301 */}
            <g
              onClick={() => setSelectedTag(TAGS[3])}
              className="cursor-pointer transition-transform hover:scale-105"
            >
              <rect x="710" y="380" width="160" height="150" rx="20" fill="#0d1117" stroke={selectedTag.id === "R-301" ? "#fbbf24" : "#384355"} strokeWidth="2.5" />
              <text x="790" y="455" textAnchor="middle" fill="#e6ebf1" fontFamily="monospace" fontSize="14" fontWeight="bold">R-301</text>
              <text x="790" y="475" textAnchor="middle" fill="#8b98ab" fontFamily="monospace" fontSize="10">HYDROTREATER</text>
            </g>

            {/* Spatial Bounding Box of currently selected tag */}
            <rect
              x={selectedTag.id === "FV-302" ? 120 : selectedTag.id === "PT-101" ? 310 : selectedTag.id === "P-101A" ? 540 : 700}
              y={selectedTag.id === "FV-302" ? 370 : selectedTag.id === "PT-101" ? 250 : selectedTag.id === "P-101A" ? 165 : 370}
              width={selectedTag.id === "FV-302" ? 90 : selectedTag.id === "PT-101" ? 80 : selectedTag.id === "P-101A" ? 120 : 180}
              height={selectedTag.id === "FV-302" ? 95 : selectedTag.id === "PT-101" ? 75 : selectedTag.id === "P-101A" ? 110 : 170}
              fill="none"
              stroke="#06b6d4"
              strokeWidth="2"
              strokeDasharray="4 2"
              className="animate-pulse"
            />
          </svg>
        </div>

        {/* Spatial Inspector Card */}
        <div className="lg:col-span-5 rounded-xl border border-surface-border bg-surface-2/70 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-border pb-3">
            <div className="flex items-center gap-2">
              <IconActivity className="h-4 w-4 text-brand" />
              <span className="font-mono text-xs font-bold text-ink-1 uppercase tracking-wider">
                Visual Inspection Inspector
              </span>
            </div>
            <span className="rounded bg-brand/15 px-2 py-0.5 font-mono text-[10px] font-bold text-brand">
              COLPALISCOPE
            </span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            <div>
              <span className="text-[10px] text-ink-3 uppercase block">Selected Equipment Tag</span>
              <span className="text-base font-bold text-brand">{selectedTag.label}</span>
            </div>

            <div>
              <span className="text-[10px] text-ink-3 uppercase block">Engineering Classification</span>
              <span className="text-ink-1 font-semibold">{selectedTag.type}</span>
            </div>

            <div>
              <span className="text-[10px] text-ink-3 uppercase block">Datasheet Specification</span>
              <span className="text-ink-2 text-[11px] leading-relaxed block">{selectedTag.spec}</span>
            </div>

            <div className="rounded border border-surface-border bg-surface-1 p-3 space-y-1.5 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-ink-3">Bounding Box:</span>
                <span className="text-ink-1 font-bold">{selectedTag.coords}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-3">Visual Match Score:</span>
                <span className="text-emerald-400 font-bold">{selectedTag.score} / 1.000</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-3">Interlocks In Line:</span>
                <span className="text-ink-1">SV-402, PT-101, FV-302</span>
              </div>
            </div>

            <p className="text-[10px] text-ink-3 font-sans leading-relaxed">
              Click any equipment bubble on the schematic to inspect its physical grounding coordinates and datasheets.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
