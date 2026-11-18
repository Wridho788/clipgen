"use client";

import { CSSProperties, RefObject, useEffect, useMemo, useRef, useState } from "react";
import { Info } from "lucide-react";

import { activeCue, captionScale, outputDimensions, renderedCues, wrapCaptionText, ZOOM_FACTOR } from "@/lib/editGeometry";
import { ClipEdit } from "@/types/api";

type EditorPreviewProps = {
  edit: ClipEdit;
  sourceUrl: string;
  fallbackUrl: string | null;
  videoRef: RefObject<HTMLVideoElement>;
  playheadMs: number;
  onSourceSize: (width: number, height: number) => void;
  sourceSize: { width: number; height: number } | null;
};

/**
 * Live 9:16 (or chosen preset) preview of the *saved-or-pending* edit, played
 * from the original source. Geometry mirrors the FFmpeg render plan; captions
 * use the same wrap/scale/position rules. Known approximations are disclosed
 * below the canvas.
 */
export function EditorPreview({
  edit,
  sourceUrl,
  fallbackUrl,
  videoRef,
  playheadMs,
  onSourceSize,
  sourceSize,
}: EditorPreviewProps) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const backgroundRef = useRef<HTMLVideoElement>(null);
  const secondaryRef = useRef<HTMLVideoElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [sourceFailed, setSourceFailed] = useState(false);

  const [outWidth, outHeight] = outputDimensions(edit, sourceSize?.width, sourceSize?.height);
  const cues = useMemo(() => renderedCues(edit), [edit]);
  const cue = activeCue(cues, playheadMs);
  const style = edit.captions.style;

  useEffect(() => {
    const element = canvasRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      setCanvasSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Keep decorative copies (blur background, split bottom) in sync with the main video.
  useEffect(() => {
    const main = videoRef.current;
    if (!main) return;
    const followers = () => [backgroundRef.current, secondaryRef.current].filter(Boolean) as HTMLVideoElement[];
    const sync = () => {
      for (const follower of followers()) {
        if (Math.abs(follower.currentTime - main.currentTime) > 0.25) follower.currentTime = main.currentTime;
        if (main.paused && !follower.paused) follower.pause();
        if (!main.paused && follower.paused) void follower.play().catch(() => undefined);
      }
    };
    const events = ["play", "pause", "seeked", "timeupdate"];
    events.forEach((name) => main.addEventListener(name, sync));
    return () => events.forEach((name) => main.removeEventListener(name, sync));
  }, [videoRef, edit.visual_style]);

  const focus = `${(edit.framing.focus_x * 100).toFixed(1)}% ${(edit.framing.focus_y * 100).toFixed(1)}%`;
  const scale = captionScale(canvasSize.width || 1, canvasSize.height || 1);
  const fontPx = Math.max(6, style.font_size * scale);
  const captionStyle: CSSProperties = {
    top: `${style.position_y * 100}%`,
    fontSize: `${fontPx}px`,
    color: style.text_color,
    fontWeight: style.bold ? 700 : 400,
    fontFamily: '"DejaVu Sans", Verdana, Arial, sans-serif',
    lineHeight: 1.2,
  };
  if (style.background === "box") {
    captionStyle.backgroundColor = style.background_color;
    captionStyle.padding = `${Math.max(1, 12 * scale)}px ${Math.max(2, 14 * scale)}px`;
  } else if (style.background === "outline") {
    const width = Math.max(1, 5 * scale);
    captionStyle.WebkitTextStroke = `${width}px ${style.background_color}`;
    captionStyle.paintOrder = "stroke fill";
  }

  const src = sourceFailed && fallbackUrl ? fallbackUrl : sourceUrl;
  const usingFallback = sourceFailed && !!fallbackUrl;
  const mainVideoStyle: CSSProperties = { objectPosition: focus };
  let mainClass = "h-full w-full object-cover";
  if (edit.output_preset === "original" || edit.visual_style === "clean" || usingFallback) {
    mainClass = "h-full w-full object-contain";
  } else if (edit.visual_style === "blur") {
    mainClass = "relative h-full w-full object-contain";
  } else if (edit.visual_style === "zoom") {
    mainVideoStyle.transform = `scale(${ZOOM_FACTOR})`;
    mainVideoStyle.transformOrigin = focus;
  }

  const showSplit = edit.visual_style === "split" && edit.output_preset !== "original" && !usingFallback;
  const showBlur = edit.visual_style === "blur" && edit.output_preset !== "original" && !usingFallback;

  return (
    <div className="space-y-2">
      <div
        ref={canvasRef}
        data-testid="editor-canvas"
        className="relative mx-auto max-h-[62vh] overflow-hidden rounded-xl bg-black shadow-inner"
        style={{ aspectRatio: `${outWidth} / ${outHeight}`, width: outWidth >= outHeight ? "100%" : undefined, height: outWidth < outHeight ? "62vh" : undefined, maxWidth: "100%" }}
      >
        {showBlur && (
          <video ref={backgroundRef} src={src} muted playsInline preload="metadata" aria-hidden className="absolute inset-0 h-full w-full scale-110 object-cover blur-lg" />
        )}
        <div className={showSplit ? "absolute inset-x-0 top-0 h-1/2 overflow-hidden" : "absolute inset-0 overflow-hidden"}>
          <video
            ref={videoRef}
            src={src}
            playsInline
            preload="metadata"
            className={mainClass}
            style={mainVideoStyle}
            onLoadedMetadata={(event) => onSourceSize(event.currentTarget.videoWidth, event.currentTarget.videoHeight)}
            onError={() => setSourceFailed(true)}
          />
        </div>
        {showSplit && (
          <div className="absolute inset-x-0 bottom-0 h-1/2 overflow-hidden">
            <video ref={secondaryRef} src={src} muted playsInline preload="metadata" aria-hidden className="h-full w-full object-cover" style={{ objectPosition: focus }} />
          </div>
        )}
        {cue && !usingFallback && (
          <div
            data-testid="caption-overlay"
            className="pointer-events-none absolute left-1/2 max-w-[94%] -translate-x-1/2 -translate-y-1/2 whitespace-pre text-center"
            style={captionStyle}
          >
            {wrapCaptionText(cue.text, style.max_chars_per_line).join("\n")}
          </div>
        )}
      </div>
      <p className="flex items-start gap-1.5 text-[11px] leading-4 text-slate-500 dark:text-slate-400">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        {usingFallback
          ? "Browser tidak bisa memutar file sumber; preview menampilkan hasil render terakhir tanpa edit yang belum dirender."
          : "Preview langsung dari video sumber memakai edit yang sama dengan render. Perkiraan: font browser, blur latar, dan watermark bisa sedikit berbeda dari MP4 hasil render."}
      </p>
    </div>
  );
}
