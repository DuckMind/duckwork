// Stand-in for the app's completion-sound store: the plugin always names the preset it plays.
export const $completionSoundVariantId = { get: () => 1 }
export function resolveCompletionSoundVariantId(v) { return Number.isInteger(v) && v >= 1 && v <= 14 ? v : 1 }
