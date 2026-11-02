"use client";

// AG Studio on PayPilot's own data. Studio owns the canvas, widgets, filters and its AI chat; this
// file wires in the data (GET /insights), the theme, the default report, PayPilot's widgets and the
// assistant. Browser only: it is loaded with next/dynamic and ssr: false.

import { AgStudioAiModule, type AgStudioApi, type AgStudioMode } from "ag-studio";
import { AgStudio, AgStudioProvider } from "ag-studio-react";
import { useMemo } from "react";
import type { InsightsData } from "@/lib/api";
import { buildAi } from "./ai";
import { buildStudioData } from "./data";
import { insightsReport } from "./report";
import { payPilotStudioTheme } from "./theme";
import { payPilotWidgets } from "./widgets";

export function InsightsStudio({
  data,
  mode,
  aiModels,
  pageId,
  onApi,
}: {
  data: InsightsData;
  mode: AgStudioMode;
  aiModels: string[] | null;
  pageId: string;
  onApi: (api: AgStudioApi) => void;
}) {
  const studioData = useMemo(() => buildStudioData(data), [data]);
  // Read once when Studio is created, like the report state.
  // The page remounts Studio when the data changes, so the assistant can close over this data.
  const ai = useMemo(() => (aiModels?.length ? buildAi(aiModels, () => data) : undefined), [aiModels, data]);
  const initialState = useMemo(() => ({ ...insightsReport, selectedPageId: pageId }), []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AgStudioProvider
      licenseKey={process.env.NEXT_PUBLIC_AG_STUDIO_LICENSE || undefined}
      modules={ai ? [AgStudioAiModule] : undefined}
    >
      <AgStudio
        style={{ height: "100%", width: "100%" }}
        theme={payPilotStudioTheme}
        layout={{ widgetBorderEnabled: true }}
        data={studioData}
        widgets={payPilotWidgets}
        ai={ai}
        initialState={initialState}
        mode={mode}
        onApiReady={(e) => onApi(e.api)}
      />
    </AgStudioProvider>
  );
}
