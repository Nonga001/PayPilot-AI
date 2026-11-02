// AG Studio theme for PayPilot. Every value points at the design tokens in app/globals.css, so the
// dashboard's canvas, widgets, grids and charts read as part of the app rather than an embed.

import { studioTheme } from "ag-studio";

const c = (name: string) => `var(--color-${name})`;
const line = (name: string) => ({ width: 1, color: c(name) });
const FONT = "var(--font-body), ui-sans-serif, system-ui, sans-serif";

// Series take colours in alphabetical order of their values, so the first four line up with the
// decisions: Answered (teal), Approved (green), Blocked (red), Review (amber).
const CHART = ["#0a8fb0", "#12805c", "#c23a2e", "#e0a63a", "#142033", "#6d5bd0", "#3fb6d3", "#8d9aab", "#58a882", "#b26b00"];
const palette = Object.fromEntries(
  CHART.flatMap((hex, i) => [
    [`chartPaletteFills${i + 1}Color`, hex],
    [`chartPaletteStrokes${i + 1}Color`, hex],
  ]),
);

export const payPilotStudioTheme = studioTheme.withParams({
  fontFamily: FONT,
  fontSize: 14,
  textColor: c("ink"),
  foregroundColor: c("ink"),
  subtleTextColor: c("muted"),
  backgroundColor: c("panel"),
  borderColor: c("line"),
  accentColor: c("ai"),
  iconColor: c("ink"),
  rowHoverColor: c("ai-soft"),

  studioWrapperBorder: false,
  studioWrapperBorderRadius: 0,
  studioWrapperSpacing: 0,
  studioWrapperBackgroundColor: c("cloud"),
  studioCanvasBorder: false,
  studioCanvasBorderRadius: 0,
  studioCanvasShadow: false,
  studioCanvasBackgroundColor: c("cloud"),
  studioCanvasPadding: 12,
  studioCanvasRowHeight: 18,
  studioCanvasFontFamily: FONT,

  // Widgets are the app's cards: white, hairline ring, 16px radius.
  studioWidgetBackgroundColor: c("panel"),
  studioWidgetBorder: line("line"),
  studioWidgetBorderRadius: 16,
  studioWidgetPadding: 12,
  studioWidgetTitleFontFamily: FONT,
  studioWidgetTitleFontSize: 15,
  studioWidgetTitleFontWeight: 600,
  studioWidgetTitleTextColor: c("ink"),
  studioWidgetSubtitleFontFamily: FONT,
  studioWidgetSubtitleFontSize: 13,
  studioWidgetSubtitleTextColor: c("muted"),
  studioWidgetCaptionFontFamily: FONT,
  studioWidgetCaptionFontSize: 12,
  studioWidgetCaptionTextColor: c("muted"),
  studioWidgetResizeBorderColor: c("ai"),

  studioPanelContainerBackgroundColor: c("panel"),
  studioPanelContainerBorder: line("line"),
  studioPanelContainerBorderRadius: 0,
  studioPanelDividerColor: c("line"),
  studioPanelDividerActiveColor: c("ai"),
  studioPanelSectionBorderColor: c("line"),
  studioPanelHeaderFontFamily: FONT,
  studioPanelHeaderFontWeight: 600,
  studioPanelChevronButtonHoverBackgroundColor: c("ai-soft"),
  studioPanelChevronButtonHoverColor: c("ai"),
  studioToggleButtonActiveBackgroundColor: c("ai-soft"),
  studioToggleButtonActiveBorderColor: c("ai"),
  studioToggleButtonActiveColor: c("ai"),

  gridFontFamily: FONT,
  gridFontSize: 14,
  gridCellTextColor: c("ink"),
  gridHeaderBackgroundColor: c("panel"),
  gridHeaderTextColor: c("muted"),
  gridHeaderFontWeight: 600,
  gridHeaderFontSize: 13,
  gridRowHeight: 38,
  gridRowBorder: line("cloud"),
  gridHeaderRowBorder: line("line"),
  gridPinnedRowBorder: line("line"),
  gridRowHoverColor: c("ai-soft"),
  gridWrapperBorder: false,

  chartFontFamily: FONT,
  chartTextColor: c("ink"),
  chartSubtleTextColor: c("muted"),
  chartAxisLineColor: c("line"),
  chartGridLineColor: c("cloud"),
  ...palette,
});
