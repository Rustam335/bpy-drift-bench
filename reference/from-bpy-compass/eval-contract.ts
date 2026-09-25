/**
 * Output-contract checks for the eval harness (issue #2).
 *
 * Running the script in Blender proves the ANSWER block works; it says nothing about the
 * WATCH OUT and SOURCES blocks. These pure functions check the rest of the contract:
 *  - WATCH OUT names every expected API change that is a trap (removed, renamed or changed
 *    behavior; an "added" API is context the output contract does not ask for);
 *  - SOURCES lists at least one Knowledge Base entry, and only entries that were actually
 *    read through knowledge_base_read during the answer.
 *
 * The WATCH OUT check is keyword-based on purpose: an `apiChange` symbol such as
 * `bpy.types.Scene.objects.link` is reduced to its last identifier (`link`) or, when the
 * symbol quotes a value (`solver == "FLOAT"`), to that quoted value. Alternatives written as
 * `a / b`, `a and b` or `a via b` count if any of them is mentioned. Matching ignores case,
 * spaces and punctuation, so `select_set`, `select set` and `Select-Set` are the same.
 */

export interface ExpectedApiChange {
  symbol: string;
  replacement?: string;
  /** "added" entries are context, not traps: WATCH OUT is defined as deprecated/removed patterns. */
  kind?: "removed" | "renamed" | "behavior" | "added";
}

export interface AnswerBlocks {
  answer: string;
  watchOut: string | null;
  sources: string | null;
}

export interface ContractResult {
  watchOutPassed: boolean;
  /** null = not applicable (no Knowledge Base, so nothing to cross-check). */
  sourcesPassed: boolean | null;
  failures: string[];
}

/** Path words that never identify an API change on their own. */
const STOP_WORDS = new Set(["bpy", "types", "ops", "none", "and", "the", "via", "attribute", "operator", "pep"]);
const ALTERNATIVE_SEPARATORS = /\s+\/\s+|\s+and\s+|\s+via\s+/;
const NO_REPLACEMENT = /^\s*\(none\)/i;
/** Dunder methods stand for their operator, which is how WATCH OUT bullets write them. */
const DUNDER_OPERATORS: Record<string, string> = { mul: "*", matmul: "@" };
/** Operator characters that identify a change on their own (kept by normalize()). */
const OPERATOR_CHARS = /[@*]/g;

export function splitBlocks(text: string): AnswerBlocks {
  const watchOutAt = text.search(/^WATCH OUT\b/m);
  const sourcesAt = text.search(/^SOURCES\b/m);
  const answerEnd = [watchOutAt, sourcesAt].filter((i) => i >= 0).sort((a, b) => a - b)[0] ?? text.length;
  const watchOut = watchOutAt >= 0 ? text.slice(watchOutAt, sourcesAt > watchOutAt ? sourcesAt : undefined) : null;
  const sources = sourcesAt >= 0 ? text.slice(sourcesAt) : null;
  return { answer: text.slice(0, answerEnd), watchOut, sources };
}

/** Lower-case alphanumerics only, so spelling variants of one identifier compare equal. */
export function normalize(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9@*]/g, "");
}

/** The tokens that identify one alternative of a symbol or replacement string. */
function keyTokensOf(alternative: string): string[] {
  const quoted = [...alternative.matchAll(/["']([^"']+)["']/g)].map((m) => m[1]);
  if (quoted.length) return [quoted[quoted.length - 1]];
  const identifiers = [...alternative.matchAll(/[A-Za-z_][A-Za-z0-9_]*/g)]
    .map((m) => m[0].replace(/^_+|_+$/g, ""))
    .filter((id) => id.length >= 3 && !STOP_WORDS.has(id.toLowerCase()));
  const last = identifiers[identifiers.length - 1];
  const tokens = last ? [last, DUNDER_OPERATORS[last.toLowerCase()]].filter((t): t is string => Boolean(t)) : [];
  return [...tokens, ...(alternative.match(OPERATOR_CHARS) ?? [])];
}

/** True when the text mentions any alternative of the given symbol/replacement string. */
export function mentions(text: string, symbolOrReplacement: string): boolean {
  const haystack = normalize(text);
  return symbolOrReplacement
    .split(ALTERNATIVE_SEPARATORS)
    .map(keyTokensOf)
    .filter((tokens) => tokens.length > 0)
    .some((tokens) => tokens.some((t) => haystack.includes(normalize(t))));
}

export function checkWatchOut(watchOut: string | null, expected: ExpectedApiChange[]): string[] {
  const traps = expected.filter((c) => c.kind !== "added");
  if (traps.length === 0) return [];
  if (watchOut === null) return ["No WATCH OUT block in the answer."];
  const failures: string[] = [];
  for (const change of traps) {
    if (!mentions(watchOut, change.symbol)) failures.push(`WATCH OUT does not mention ${change.symbol}.`);
    const replacement = change.replacement?.trim();
    if (replacement && !NO_REPLACEMENT.test(replacement) && !mentions(watchOut, replacement)) {
      failures.push(`WATCH OUT does not name the replacement for ${change.symbol} (${replacement}).`);
    }
  }
  return failures;
}

/** Entry paths listed under SOURCES, one per "- " bullet; "none" yields an empty list. */
export function parseSources(sources: string | null): string[] {
  if (sources === null) return [];
  return sources
    .split("\n")
    .slice(1)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).replace(/`/g, "").split(/\s/)[0].trim())
    .filter((path) => path && path.toLowerCase() !== "none");
}

export function checkSources(sources: string | null, readPaths: string[]): string[] {
  if (sources === null) return ["No SOURCES block in the answer."];
  const listed = parseSources(sources);
  if (listed.length === 0) return ["SOURCES lists no Knowledge Base entry."];
  const read = new Set(readPaths.map((p) => p.trim()));
  return listed.filter((p) => !read.has(p)).map((p) => `SOURCES lists "${p}", which was not read from the Knowledge Base.`);
}

/**
 * Check the WATCH OUT and SOURCES blocks of one answer.
 * `readPaths` is the list of entry paths passed to knowledge_base_read during the answer, or
 * null for a contender without a Knowledge Base (the sources check is then not applicable).
 */
export function checkContract(opts: { answer: string; expected: ExpectedApiChange[]; readPaths: string[] | null }): ContractResult {
  const blocks = splitBlocks(opts.answer);
  const watchOutFailures = checkWatchOut(blocks.watchOut, opts.expected);
  const sourcesFailures = opts.readPaths === null ? [] : checkSources(blocks.sources, opts.readPaths);
  return {
    watchOutPassed: watchOutFailures.length === 0,
    sourcesPassed: opts.readPaths === null ? null : sourcesFailures.length === 0,
    failures: [...watchOutFailures, ...sourcesFailures],
  };
}
