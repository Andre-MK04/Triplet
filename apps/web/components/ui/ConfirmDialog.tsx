"use client";

import { useEffect, useState } from "react";

import { Button } from "./Button";
import { Dialog } from "./Dialog";

/**
 * A modal for a decision that cannot be undone.
 *
 * window.confirm() is unstyled, cannot show what is actually being destroyed,
 * and in some browsers is suppressible entirely — which for account deletion
 * means the safeguard may simply not appear.
 *
 * The modal mechanics live in Dialog; what is left here is the part specific to
 * destruction: spelling out the consequences, and where `confirmPhrase` is set,
 * refusing to proceed until the exact phrase is typed. That friction is
 * deliberate and reserved for actions with no undo.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  confirmPhrase,
  onConfirm,
  onCancel,
  isWorking = false,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  confirmPhrase?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isWorking?: boolean;
}) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const phraseSatisfied = !confirmPhrase || typed.trim() === confirmPhrase;

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      size="sm"
      footer={
        <div className="flex flex-wrap justify-end gap-3">
          {/* Cancel first, so the destructive action is never the thing focus
              or a stray Enter lands on. */}
          <Button variant="secondary" onClick={onCancel} disabled={isWorking}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={!phraseSatisfied || isWorking}>
            {isWorking ? "Working…" : confirmLabel}
          </Button>
        </div>
      }
    >
      <div className="space-y-3 text-sm leading-relaxed text-mist">{children}</div>

      {confirmPhrase ? (
        <label className="mt-5 block">
          <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
            Type <span className="text-coral">{confirmPhrase}</span> to continue
          </span>
          <input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            autoComplete="off"
            // A slip of the keyboard should not be able to satisfy this.
            spellCheck={false}
            className="cmd-input mt-2 w-full py-2 font-mono text-sm text-cloud"
            aria-label={`Type ${confirmPhrase} to confirm`}
          />
        </label>
      ) : null}
    </Dialog>
  );
}
