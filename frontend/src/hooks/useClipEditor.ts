"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api";
import { ClipEdit, ClipResponse } from "@/types/api";

export type SaveState = "saved" | "dirty" | "saving" | "error" | "conflict";

const AUTOSAVE_DELAY_MS = 700;
const HISTORY_LIMIT = 60;

/**
 * Local draft of a clip's canonical edit with debounced autosave.
 *
 * - Saves send the revision the draft is based on; the server rejects stale
 *   writes (409 EDIT_CONFLICT) instead of overwriting newer work.
 * - Server refreshes (polling) never clobber unsaved local changes.
 * - Undo/redo operate on the edit document only — the source is immutable.
 *
 * Mount one instance per clip (``key={clip.id}``); unmounting flushes any
 * pending save for that clip.
 */
export function useClipEditor(clip: ClipResponse) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<ClipEdit | null>(clip.edit || null);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [saveError, setSaveError] = useState<string | null>(null);
  // History lives in refs; ``historyVersion`` only triggers re-renders so the
  // undo/redo buttons update. (State updaters must stay side-effect free.)
  const pastRef = useRef<ClipEdit[]>([]);
  const futureRef = useRef<ClipEdit[]>([]);
  const [historyVersion, setHistoryVersion] = useState(0);

  const revisionRef = useRef<number>(clip.edit_revision || 0);
  const draftRef = useRef<ClipEdit | null>(clip.edit || null);
  const dirtyRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlightRef = useRef<Promise<boolean> | null>(null);
  const clipIdRef = useRef(clip.id);

  const writeCache = useCallback(
    (updated: ClipResponse) => {
      queryClient.setQueryData<ClipResponse[]>(["clips", updated.job_id], (current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)),
      );
    },
    [queryClient],
  );

  const save = useCallback(async (): Promise<boolean> => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (inFlightRef.current) await inFlightRef.current;
    if (!dirtyRef.current || !draftRef.current) return true;
    const clipId = clipIdRef.current;
    const snapshot = draftRef.current;
    dirtyRef.current = false;
    setSaveState("saving");
    const request = api
      .saveClipEdit(clipId, revisionRef.current, snapshot)
      .then((updated) => {
        if (clipIdRef.current !== clipId) return true;
        revisionRef.current = updated.edit_revision || revisionRef.current + 1;
        writeCache(updated);
        if (!dirtyRef.current && updated.edit) {
          // Adopt server normalisation (e.g. uppercase colours) when the
          // user has not typed anything since the request left.
          draftRef.current = updated.edit;
          setDraft(updated.edit);
        }
        setSaveError(null);
        setSaveState(dirtyRef.current ? "dirty" : "saved");
        return true;
      })
      .catch((error: unknown) => {
        if (clipIdRef.current !== clipId) return false;
        if (error instanceof ApiError && error.code === "EDIT_CONFLICT") {
          setSaveState("conflict");
          setSaveError("Klip ini sudah diubah di tab/sesi lain. Muat versi terbaru sebelum melanjutkan.");
          return false;
        }
        dirtyRef.current = true;
        setSaveState("error");
        setSaveError(error instanceof Error ? error.message : "Gagal menyimpan edit");
        return false;
      })
      .finally(() => {
        inFlightRef.current = null;
      });
    inFlightRef.current = request;
    const ok = await request;
    if (ok && dirtyRef.current) return save();
    return ok;
  }, [writeCache]);

  const schedule = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      void save();
    }, AUTOSAVE_DELAY_MS);
  }, [save]);

  const update = useCallback(
    (producer: (current: ClipEdit) => ClipEdit, options: { history?: boolean } = {}) => {
      const current = draftRef.current;
      if (!current) return;
      const next = producer(current);
      if (next === current) return;
      if (options.history !== false) {
        pastRef.current = [...pastRef.current.slice(-(HISTORY_LIMIT - 1)), current];
        futureRef.current = [];
        setHistoryVersion((value) => value + 1);
      }
      draftRef.current = next;
      dirtyRef.current = true;
      setDraft(next);
      setSaveState((state) => (state === "conflict" ? state : "dirty"));
      schedule();
    },
    [schedule],
  );

  const applyHistory = useCallback(
    (target: ClipEdit) => {
      draftRef.current = target;
      dirtyRef.current = true;
      setDraft(target);
      setSaveState("dirty");
      setHistoryVersion((value) => value + 1);
      schedule();
    },
    [schedule],
  );

  const undo = useCallback(() => {
    const current = draftRef.current;
    const previous = pastRef.current[pastRef.current.length - 1];
    if (!current || !previous) return;
    pastRef.current = pastRef.current.slice(0, -1);
    futureRef.current = [current, ...futureRef.current].slice(0, HISTORY_LIMIT);
    applyHistory(previous);
  }, [applyHistory]);

  const redo = useCallback(() => {
    const current = draftRef.current;
    const [next, ...rest] = futureRef.current;
    if (!current || !next) return;
    futureRef.current = rest;
    pastRef.current = [...pastRef.current, current].slice(-HISTORY_LIMIT);
    applyHistory(next);
  }, [applyHistory]);

  const resetHistory = useCallback(() => {
    pastRef.current = [];
    futureRef.current = [];
    setHistoryVersion((value) => value + 1);
  }, []);

  const reloadFromServer = useCallback(async () => {
    const fresh = await api.getClip(clipIdRef.current);
    revisionRef.current = fresh.edit_revision || 0;
    draftRef.current = fresh.edit || null;
    dirtyRef.current = false;
    setDraft(fresh.edit || null);
    resetHistory();
    setSaveError(null);
    setSaveState("saved");
    writeCache(fresh);
  }, [resetHistory, writeCache]);

  // Adopt newer server revisions (another tab, trim endpoint) when clean.
  useEffect(() => {
    if (clip.id !== clipIdRef.current) return;
    const serverRevision = clip.edit_revision || 0;
    if (serverRevision > revisionRef.current && !dirtyRef.current && !inFlightRef.current) {
      revisionRef.current = serverRevision;
      draftRef.current = clip.edit || null;
      setDraft(clip.edit || null);
    }
  }, [clip.id, clip.edit, clip.edit_revision]);

  // Warn before closing the tab with unsaved edits; flush on unmount.
  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirtyRef.current && !inFlightRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      if (dirtyRef.current) void save();
    };
  }, [save]);

  return {
    draft,
    update,
    save,
    saveState,
    saveError,
    undo,
    redo,
    canUndo: historyVersion >= 0 && pastRef.current.length > 0,
    canRedo: historyVersion >= 0 && futureRef.current.length > 0,
    reloadFromServer,
    revision: revisionRef.current,
  };
}
