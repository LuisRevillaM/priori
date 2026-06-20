import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
function isObject(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
function asObject(value, label) {
    if (!isObject(value)) {
        throw new Error(`${label} must be an object`);
    }
    return value;
}
function asArray(value, label) {
    if (!Array.isArray(value)) {
        throw new Error(`${label} must be an array`);
    }
    return value;
}
function asString(value, label) {
    if (typeof value !== "string") {
        throw new Error(`${label} must be a string`);
    }
    return value;
}
function asNumber(value, label) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
        throw new Error(`${label} must be a finite number`);
    }
    return value;
}
function readJson(path) {
    const parsed = JSON.parse(readFileSync(path, "utf8"));
    if (!isObject(parsed)) {
        throw new Error(`${path} must contain a JSON object`);
    }
    return parsed;
}
function check(status, id, message, evidence) {
    return evidence === undefined ? { id, status, message } : { id, status, message, evidence };
}
function resolveRepoPath(repoRoot, value) {
    return isAbsolute(value) ? value : resolve(repoRoot, value);
}
function bundleRecords(manifest, repoRoot) {
    return asArray(manifest.evidence_bundles, "manifest.evidence_bundles").map((entry, index) => {
        const record = asObject(entry, `manifest.evidence_bundles[${index}]`);
        return {
            resultId: asString(record.result_id, `bundle[${index}].result_id`),
            bundleJson: resolveRepoPath(repoRoot, asString(record.bundle_json, `bundle[${index}].bundle_json`)),
            replayJson: resolveRepoPath(repoRoot, asString(record.replay_json, `bundle[${index}].replay_json`))
        };
    });
}
function validateReplay(record, bundle, replay) {
    const checks = [];
    const bundleQuery = asObject(bundle.query, "bundle.query");
    const replayPitch = asObject(replay.pitch, "replay.pitch");
    const frames = asArray(replay.frames, "replay.frames");
    const pitchLength = asNumber(replayPitch.length_m, "replay.pitch.length_m");
    const pitchWidth = asNumber(replayPitch.width_m, "replay.pitch.width_m");
    const halfLength = pitchLength / 2 + 5;
    const halfWidth = pitchWidth / 2 + 5;
    let entityCount = 0;
    let invalidCoordinateCount = 0;
    let ballFrameCount = 0;
    for (const [frameIndex, frameValue] of frames.entries()) {
        const frame = asObject(frameValue, `replay.frames[${frameIndex}]`);
        const entities = asArray(frame.entities, `replay.frames[${frameIndex}].entities`);
        const hasBall = entities.some((entityValue) => {
            const entity = asObject(entityValue, "entity");
            const x = asNumber(entity.x_m, "entity.x_m");
            const y = asNumber(entity.y_m, "entity.y_m");
            entityCount += 1;
            if (Math.abs(x) > halfLength || Math.abs(y) > halfWidth) {
                invalidCoordinateCount += 1;
            }
            return entity.entity_type === "ball";
        });
        if (hasBall) {
            ballFrameCount += 1;
        }
    }
    checks.push(check(bundle.result_id === record.resultId && replay.result_id === record.resultId ? "pass" : "fail", `replay.${record.resultId}.result_id`, "Bundle and replay reference the manifest result id.", record.bundleJson));
    checks.push(check(typeof bundleQuery.query_hash === "string" && bundleQuery.query_hash.length === 64 ? "pass" : "fail", `replay.${record.resultId}.query_hash`, "Bundle carries a frozen query hash.", record.bundleJson));
    checks.push(check(frames.length > 0 && entityCount > 0 ? "pass" : "fail", `replay.${record.resultId}.nonempty`, "Replay contains frames and entity observations.", record.replayJson));
    checks.push(check(ballFrameCount === frames.length ? "pass" : "fail", `replay.${record.resultId}.ball_present`, "Every replay frame includes a ball observation.", record.replayJson));
    checks.push(check(invalidCoordinateCount === 0 ? "pass" : "fail", `replay.${record.resultId}.coordinate_bounds`, "Replay coordinates stay within pitch plus tolerance.", record.replayJson));
    return checks;
}
function main() {
    const manifestPath = process.argv[2] ?? "../../artifacts/m1/gate-c/proof-pack-manifest.json";
    const reportPath = process.argv[3] ?? "../../artifacts/m1/gate-c/replay-proof-report.json";
    const checks = [];
    const manifest = readJson(manifestPath);
    const manifestAbsolutePath = resolve(process.cwd(), manifestPath);
    const repoRoot = resolve(dirname(manifestAbsolutePath), "../../..");
    const records = bundleRecords(manifest, repoRoot);
    checks.push(check(manifest.status === "pass" ? "pass" : "fail", "manifest.status", "Proof manifest reports pass.", manifestPath));
    checks.push(check(records.length >= 8 && records.length === asNumber(manifest.selected_result_count, "manifest.selected_result_count")
        ? "pass"
        : "fail", "manifest.selected_result_count", "Manifest records the selected evidence-bundle count.", manifestPath));
    for (const record of records) {
        const bundle = readJson(record.bundleJson);
        const replay = readJson(record.replayJson);
        checks.push(...validateReplay(record, bundle, replay));
    }
    const summary = {
        pass: checks.filter((item) => item.status === "pass").length,
        fail: checks.filter((item) => item.status === "fail").length
    };
    const status = summary.fail === 0 ? "pass" : "fail";
    mkdirSync(dirname(reportPath), { recursive: true });
    writeFileSync(reportPath, `${JSON.stringify({
        schema_version: "1.0",
        status,
        generated_at: new Date().toISOString(),
        manifest_path: manifestPath,
        summary,
        checks
    }, null, 2)}\n`, "utf8");
    console.log(JSON.stringify({ status, summary }));
    return status === "pass" ? 0 : 1;
}
process.exitCode = main();
