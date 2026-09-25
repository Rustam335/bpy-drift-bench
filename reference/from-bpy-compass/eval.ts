/**
 * Eval harness: baseline (no tools) vs bpy-compass (KB tools) on every `testCase`,
 * executed in headless Blender, results written to Sanity as `evalRun` documents.
 *
 *   yarn eval                 run everything and write results
 *   yarn eval --dry-run       run, print, do not write to Sanity
 *   yarn eval --only 3        run only test case #3 (by `order`)
 *
 * Runs locally only (Blender is not available on Vercel).
 */
import "./load-env";
import { generateText, stepCountIs } from "ai";
import { spawnSync } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { connectContextMcp, fetchInitialContext } from "../lib/context-mcp";
import { env } from "../lib/env";
import { checkContract } from "../lib/eval-contract";
import { blenderReason } from "../lib/eval-runs";
import {
  assertValidModelConfig,
  createChatModel,
  MAX_OUTPUT_TOKENS,
  MAX_STEPS,
  MODEL_ID,
  PROVIDER,
  REASONING_MAX_TOKENS,
  TEMPERATURE,
  type Contender,
} from "../lib/model";
import { buildBaselinePrompt, buildSystemPrompt, buildUserPrompt } from "../lib/prompt";
import { fetchTestCases, writeClient, type TestCaseDoc } from "../lib/sanity";

const BLENDER_TIMEOUT_MS = 120_000;

type RunResult = {
  script: string;
  rawAnswer: string;
  /** blenderPassed && watchOutPassed && sourcesPassed !== false */
  passed: boolean;
  blenderPassed: boolean;
  watchOutPassed: boolean;
  /** null for the baseline (no Knowledge Base to cross-check). */
  sourcesPassed: boolean | null;
  failures: string[];
  stderr: string;
  blenderBuild: string;
};

/** What one contender produced: the text plus the KB entry paths it actually read (null = no KB). */
type Answer = { text: string; readPaths: string[] | null };

/* ---------- CLI ---------- */

export function parseArgs(argv: string[]): { dryRun: boolean; only?: number } {
  const dryRun = argv.includes("--dry-run");
  const onlyIdx = argv.indexOf("--only");
  if (onlyIdx < 0) return { dryRun };
  // A typo here must not silently run the whole suite (issue #7).
  const raw = argv[onlyIdx + 1];
  if (!raw || !/^[1-9]\d*$/.test(raw)) {
    throw new Error(`--only expects a positive integer test-case order, got "${raw ?? ""}".`);
  }
  return { dryRun, only: Number(raw) };
}

/* ---------- LLM ---------- */

function model() {
  return createChatModel({ reasoningMaxTokens: REASONING_MAX_TOKENS });
}

/** Same prompt, contract and settings as the compass; the only thing missing is the Knowledge Base (issue #3). */
async function askBaseline(tc: TestCaseDoc): Promise<Answer> {
  const { text } = await generateText({
    model: model(),
    system: buildBaselinePrompt(tc.targetVersion),
    prompt: buildUserPrompt(tc.targetVersion, tc.question),
    temperature: TEMPERATURE,
    maxOutputTokens: MAX_OUTPUT_TOKENS,
  });
  return { text, readPaths: null };
}

/** Entry paths passed to knowledge_base_read across all steps, so SOURCES can be cross-checked (issue #2). */
export function readPathsOf(steps: { toolCalls: { toolName: string; input: unknown }[] }[]): string[] {
  return steps.flatMap((step) =>
    step.toolCalls
      .filter((call) => call.toolName === "knowledge_base_read")
      .flatMap((call) => {
        const paths = (call.input as { paths?: unknown } | null)?.paths;
        return Array.isArray(paths) ? paths.filter((p): p is string => typeof p === "string") : [];
      }),
  );
}

async function askCompass(tc: TestCaseDoc, outline: string): Promise<Answer> {
  const mcp = await connectContextMcp();
  try {
    const { text, steps } = await generateText({
      model: model(),
      system: buildSystemPrompt({ version: tc.targetVersion, outline }),
      prompt: buildUserPrompt(tc.targetVersion, tc.question),
      tools: await mcp.tools(),
      stopWhen: stepCountIs(MAX_STEPS),
      temperature: TEMPERATURE,
      maxOutputTokens: MAX_OUTPUT_TOKENS,
    });
    return { text, readPaths: readPathsOf(steps) };
  } finally {
    await mcp.close();
  }
}

/**
 * Pull the python script out of an answer. Accepts either a fenced ```python block
 * (baseline) or the 4-space-indented block under "ANSWER" (bpy-compass format).
 */
export function extractScript(answer: string): string {
  const fenced = answer.match(/```(?:python|py)?\s*\n([\s\S]*?)```/);
  if (fenced) return fenced[1].trimEnd();

  const answerBlock = answer.split(/\n(?:WATCH OUT|SOURCES)\b/)[0];
  const indented = answerBlock
    .split("\n")
    .filter((line) => line.startsWith("    "))
    .map((line) => line.slice(4));
  return indented.join("\n").trim();
}

/* ---------- Blender ---------- */

/** Verified `major.minor` -> build string, so each binary is probed once per run. */
const verifiedBuilds = new Map<string, string>();

/**
 * Resolve the exact Blender build for a target version and verify it before use, so an
 * `evalRun` for target X.Y can only ever come from a Blender X.Y runtime (issue #1).
 */
function blenderFor(targetVersion: string): { bin: string; build: string } {
  const { name, path: bin } = env.blender.binFor(targetVersion);
  if (!bin) throw new Error(`No Blender binary configured for target ${targetVersion}: set ${name} in .env.local.`);

  const cached = verifiedBuilds.get(targetVersion);
  if (cached) return { bin, build: cached };

  const out = spawnSync(bin, ["--version"], { encoding: "utf8" });
  // Some builds print allocator notices first, so take the first line that names the build.
  const firstLine = (out.stdout ?? "").split("\n").map((l) => l.trim()).find((l) => l.startsWith("Blender ")) ?? "";
  const runtime = /^Blender (\d+\.\d+)/.exec(firstLine)?.[1];
  if (!runtime) throw new Error(`${name}=${bin} did not report a Blender version (got: "${out.stdout?.trim() || out.error?.message || ""}").`);
  if (runtime !== targetVersion) {
    throw new Error(`${name} is Blender ${runtime}, but test cases targeting ${targetVersion} need a ${targetVersion} build.`);
  }

  verifiedBuilds.set(targetVersion, firstLine);
  return { bin, build: firstLine };
}

async function runInBlender(bin: string, script: string, assertScript?: string) {
  // One scratch directory per execution, removed after the result is collected (issue #13).
  const dir = await mkdtemp(path.join(tmpdir(), "bpy-compass-"));
  try {
    const file = path.join(dir, "case.py");
    const body = [script, "", "# ---- assertions ----", assertScript ?? ""].join("\n");
    await writeFile(file, body, "utf8");

    const out = spawnSync(bin, ["-b", "--factory-startup", "--python-exit-code", "1", "--python", file], {
      encoding: "utf8",
      timeout: BLENDER_TIMEOUT_MS,
      // Test cases that write files read this path instead of inventing one.
      env: { ...process.env, BPY_OUT_OBJ: path.join(dir, "out.obj") },
    });
    return { passed: out.status === 0, stderr: (out.stderr ?? "") + (out.error ? `\n${out.error.message}` : "") };
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

/* ---------- Orchestration ---------- */

/**
 * One contender on one test case: the script must run in the exact Blender build AND the
 * WATCH OUT / SOURCES blocks must hold up (issue #2). Both verdicts are stored separately.
 */
async function evaluate(tc: TestCaseDoc, contender: Contender, outline: string): Promise<RunResult> {
  const { text: rawAnswer, readPaths } = contender === "baseline" ? await askBaseline(tc) : await askCompass(tc, outline);
  const contract = checkContract({ answer: rawAnswer, expected: tc.expectApiChanges ?? [], readPaths });
  const script = extractScript(rawAnswer);
  const blender = script
    ? await runScript(tc, script)
    : { passed: false, stderr: "No python script found in answer.", build: "n/a" };

  const failures = [...contract.failures, ...(blender.passed ? [] : [`Blender: ${blenderReason(blender.stderr)}`])];
  return {
    script,
    rawAnswer,
    passed: blender.passed && contract.watchOutPassed && contract.sourcesPassed !== false,
    blenderPassed: blender.passed,
    watchOutPassed: contract.watchOutPassed,
    sourcesPassed: contract.sourcesPassed,
    failures,
    stderr: blender.stderr,
    blenderBuild: blender.build,
  };
}

async function runScript(tc: TestCaseDoc, script: string) {
  const { bin, build } = blenderFor(tc.targetVersion);
  return { ...(await runInBlender(bin, script, tc.assertScript)), build };
}

function evalRunDoc(tc: TestCaseDoc, contender: Contender, r: RunResult, runId: string) {
  return {
    _id: `evalRun-${runId}-${tc._id}-${contender}`,
    _type: "evalRun",
    runId,
    testCase: { _type: "reference", _ref: tc._id },
    contender,
    script: { _type: "code", language: "python", code: r.script },
    rawAnswer: r.rawAnswer,
    passed: r.passed,
    blenderPassed: r.blenderPassed,
    watchOutPassed: r.watchOutPassed,
    ...(r.sourcesPassed === null ? {} : { sourcesPassed: r.sourcesPassed }),
    failures: r.failures,
    stderr: r.stderr.slice(0, 4000),
    blenderBuild: r.blenderBuild,
    modelId: MODEL_ID,
    provider: PROVIDER,
    temperature: TEMPERATURE,
    ranAt: new Date().toISOString(),
  };
}

async function main() {
  const { dryRun, only } = parseArgs(process.argv.slice(2));
  assertValidModelConfig();

  const all = await fetchTestCases({ fresh: true });
  if (all.length === 0) throw new Error("No test cases found in Sanity.");
  const cases = only === undefined ? all : all.filter((tc) => tc.order === only);
  if (cases.length === 0) throw new Error(`No test case has order ${only}. Available: ${all.map((tc) => tc.order).join(", ")}.`);

  // Fail before any LLM call if a required Blender build is missing or the wrong version.
  for (const targetVersion of new Set(cases.map((tc) => tc.targetVersion))) {
    console.log(`blender ${targetVersion} -> ${blenderFor(targetVersion).build}`);
  }

  const outline = await fetchInitialContext();
  const runId = new Date().toISOString().replace(/[:.]/g, "-");
  const client = dryRun ? null : writeClient();

  console.log(`model=${MODEL_ID} provider=${PROVIDER} temperature=${TEMPERATURE} cases=${cases.length}`);

  for (const [i, tc] of cases.entries()) {
    for (const contender of ["baseline", "bpy-compass"] as const) {
      const r = await evaluate(tc, contender, outline);
      console.log(`#${tc.order ?? i + 1} [${tc.targetVersion}] ${contender.padEnd(11)} ${r.passed ? "PASS" : "FAIL"}  ${tc.question}`);
      for (const f of r.failures) console.log(`   ${f}`);
      if (client) await client.createOrReplace(evalRunDoc(tc, contender, r, runId));
    }
  }
}

if (process.argv[1] && /eval\.ts$/.test(process.argv[1])) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
