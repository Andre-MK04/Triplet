/** Decorative globes still need an enabled controller for auto-rotation. */
export function globeControlsEnabled(interactive: boolean, shouldAnimate: boolean): boolean {
  return interactive || shouldAnimate;
}
