"""Generate the Gate A 30-second replay bundle and screenshot from canonical data."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq
from PIL import Image, ImageDraw, ImageFont

MATCH_ID = "J03WOH"
PERIOD = "firstHalf"
DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")
DEFAULT_ARTIFACT_DIR = Path("artifacts/m1/gate-a")
FRAME_RATE_HZ = 25
REPLAY_SECONDS = 30
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filter_frame_window(table, start_frame_id: int, end_frame_id: int):
    mask = pc.and_(
        pc.greater_equal(table["frame_id"], start_frame_id),
        pc.less_equal(table["frame_id"], end_frame_id),
    )
    return table.filter(mask)


def load_replay_window(canonical_root: Path) -> dict[str, Any]:
    frame_path = canonical_root / "frames" / f"match_id={MATCH_ID}" / f"period={PERIOD}.parquet"
    position_path = canonical_root / "positions" / f"match_id={MATCH_ID}" / f"period={PERIOD}.parquet"
    orientation_path = canonical_root / "orientation.parquet"
    for path in (frame_path, position_path, orientation_path):
        if not path.exists():
            raise FileNotFoundError(path)

    frames = pq.ParquetFile(frame_path).read()
    frame_ids = frames["frame_id"].to_pylist()
    start_frame_id = int(frame_ids[0])
    end_frame_id = start_frame_id + (FRAME_RATE_HZ * REPLAY_SECONDS) - 1
    frames = filter_frame_window(frames, start_frame_id, end_frame_id)
    positions = filter_frame_window(pq.ParquetFile(position_path).read(), start_frame_id, end_frame_id)
    orientation = pq.ParquetFile(orientation_path).read().to_pylist()

    positions_by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in positions.to_pylist():
        positions_by_frame.setdefault(int(row["frame_id"]), []).append(
            {
                "team_id": row["team_id"],
                "team_role": row["team_role"],
                "entity_id": row["entity_id"],
                "entity_type": row["entity_type"],
                "x_m": round(float(row["x_m"]), 3),
                "y_m": round(float(row["y_m"]), 3),
            }
        )

    replay_frames: list[dict[str, Any]] = []
    for frame in frames.to_pylist():
        frame_id = int(frame["frame_id"])
        replay_frames.append(
            {
                "frame_id": frame_id,
                "timestamp_utc": frame["timestamp_utc"],
                "entities": positions_by_frame.get(frame_id, []),
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "match_id": MATCH_ID,
        "period": PERIOD,
        "frame_rate_hz": FRAME_RATE_HZ,
        "duration_seconds": REPLAY_SECONDS,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "pitch": {
            "length_m": PITCH_LENGTH_M,
            "width_m": PITCH_WIDTH_M,
            "coordinate_contract": "centered_metres",
        },
        "canonical_sources": {
            "frames": str(frame_path),
            "positions": str(position_path),
            "orientation": str(orientation_path),
            "frames_sha256": sha256_file(frame_path),
            "positions_sha256": sha256_file(position_path),
            "orientation_sha256": sha256_file(orientation_path),
        },
        "orientation": orientation,
        "frames": replay_frames,
    }


def pitch_to_pixel(x_m: float, y_m: float, width: int, height: int, margin: int) -> tuple[float, float]:
    inner_width = width - margin * 2
    inner_height = height - margin * 2
    x = margin + ((x_m + PITCH_LENGTH_M / 2.0) / PITCH_LENGTH_M) * inner_width
    y = margin + ((PITCH_WIDTH_M / 2.0 - y_m) / PITCH_WIDTH_M) * inner_height
    return x, y


def draw_pitch(draw: ImageDraw.ImageDraw, width: int, height: int, margin: int) -> None:
    line = (235, 245, 235)
    left = margin
    top = margin
    right = width - margin
    bottom = height - margin
    mid_x = (left + right) / 2
    mid_y = (top + bottom) / 2
    draw.rectangle((left, top, right, bottom), outline=line, width=3)
    draw.line((mid_x, top, mid_x, bottom), fill=line, width=2)
    draw.ellipse((mid_x - 65, mid_y - 65, mid_x + 65, mid_y + 65), outline=line, width=2)
    draw.rectangle((left, mid_y - 115, left + 165, mid_y + 115), outline=line, width=2)
    draw.rectangle((right - 165, mid_y - 115, right, mid_y + 115), outline=line, width=2)
    draw.rectangle((left, mid_y - 58, left + 55, mid_y + 58), outline=line, width=2)
    draw.rectangle((right - 55, mid_y - 58, right, mid_y + 58), outline=line, width=2)


def render_screenshot(replay: dict[str, Any], screenshot_path: Path) -> None:
    width = 1200
    height = 820
    margin = 70
    image = Image.new("RGB", (width, height), (31, 109, 63))
    draw = ImageDraw.Draw(image)
    draw_pitch(draw, width, height, margin)

    frame = replay["frames"][len(replay["frames"]) // 2]
    for entity in frame["entities"]:
        x, y = pitch_to_pixel(float(entity["x_m"]), float(entity["y_m"]), width, height, margin)
        if entity["entity_type"] == "ball":
            fill = (255, 214, 10)
            outline = (35, 35, 35)
            radius = 7
        elif entity["team_role"] == "home":
            fill = (159, 25, 34)
            outline = (255, 255, 255)
            radius = 9
        else:
            fill = (245, 245, 245)
            outline = (35, 35, 35)
            radius = 9
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=outline, width=2)

    title = f"{MATCH_ID} Gate A Replay | {PERIOD} | frame {frame['frame_id']}"
    try:
        font = ImageFont.truetype("Arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.rectangle((margin, 22, width - margin, 56), fill=(20, 72, 43))
    draw.text((margin + 14, 31), title, fill=(255, 255, 255), font=font)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(screenshot_path)


def write_replay_html(path: Path) -> None:
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Gate A Replay</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html, body { margin: 0; height: 100%; background: #163f2a; color: #f7faf7; font-family: system-ui, sans-serif; }
    body { display: grid; place-items: center; }
    canvas { width: min(96vw, 1200px); aspect-ratio: 105 / 68; background: #1f6d3f; }
  </style>
</head>
<body>
  <canvas id="pitch" width="1200" height="777"></canvas>
  <script>
    const canvas = document.getElementById('pitch');
    const ctx = canvas.getContext('2d');
    fetch('./replay.json').then(r => r.json()).then(replay => {
      let i = 0;
      function px(x, y) {
        const m = 55;
        return [
          m + ((x + 52.5) / 105) * (canvas.width - m * 2),
          m + ((34 - y) / 68) * (canvas.height - m * 2)
        ];
      }
      function drawPitch() {
        ctx.fillStyle = '#1f6d3f';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = '#edf7ed';
        ctx.lineWidth = 3;
        const m = 55, w = canvas.width, h = canvas.height, midX = w / 2, midY = h / 2;
        ctx.strokeRect(m, m, w - m * 2, h - m * 2);
        ctx.beginPath(); ctx.moveTo(midX, m); ctx.lineTo(midX, h - m); ctx.stroke();
        ctx.beginPath(); ctx.arc(midX, midY, 65, 0, Math.PI * 2); ctx.stroke();
      }
      function draw() {
        const frame = replay.frames[i % replay.frames.length];
        drawPitch();
        for (const e of frame.entities) {
          const [x, y] = px(e.x_m, e.y_m);
          const ball = e.entity_type === 'ball';
          ctx.beginPath();
          ctx.fillStyle = ball ? '#ffd60a' : (e.team_role === 'home' ? '#9f1922' : '#f5f5f5');
          ctx.strokeStyle = ball ? '#222' : (e.team_role === 'home' ? '#fff' : '#222');
          ctx.lineWidth = 2;
          ctx.arc(x, y, ball ? 6 : 8, 0, Math.PI * 2);
          ctx.fill(); ctx.stroke();
        }
        i += 1;
        requestAnimationFrame(draw);
      }
      draw();
    });
  </script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def build_replay(canonical_root: Path, artifact_dir: Path) -> dict[str, Any]:
    bundle_dir = artifact_dir / "replay-bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    replay = load_replay_window(canonical_root)
    replay_path = bundle_dir / "replay.json"
    write_json(replay_path, replay)
    write_replay_html(bundle_dir / "index.html")

    screenshot_path = artifact_dir / "replay-screenshot.png"
    render_screenshot(replay, screenshot_path)
    manifest = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": "pass",
        "match_id": MATCH_ID,
        "period": PERIOD,
        "duration_seconds": REPLAY_SECONDS,
        "frame_count": len(replay["frames"]),
        "entity_observation_count": sum(len(frame["entities"]) for frame in replay["frames"]),
        "replay_json": str(replay_path),
        "replay_json_sha256": sha256_file(replay_path),
        "index_html": str(bundle_dir / "index.html"),
        "screenshot": str(screenshot_path),
        "screenshot_sha256": sha256_file(screenshot_path),
        "source": replay["canonical_sources"],
    }
    write_json(bundle_dir / "manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-root", default=str(DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_replay(Path(args.canonical_root), Path(args.artifact_dir))
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "frame_count": manifest["frame_count"],
                "entity_observation_count": manifest["entity_observation_count"],
                "screenshot": manifest["screenshot"],
            },
            sort_keys=True,
        )
    )
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
