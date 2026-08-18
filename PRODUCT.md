# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase: Python/Flask backend (`app/server.py`), server-rendered HTML template (`app/templates/index.html`) with vanilla JS/CSS (`app/static/`). No frontend framework or build step. This page extends that existing stack.

## Users

The primary user is the person running this tool locally (currently the developer/operator themself, working from a Bangladeshi road-traffic context) to process CCTV/dashcam footage and produce a vehicle count report. They run the tool on their own machine (Linux dev box now, deploying to a Windows client PC), pick or upload a video file, and want to watch the count happen live rather than wait blind for a finished report. Non-technical stakeholders (a "client") receive the finished PDF/Excel output, not the live tool.

## Product Purpose

Detects, classifies, and counts vehicles crossing user-defined lines/boundary in traffic video footage — including region-specific vehicle types (rickshaw, CNG/auto-rickshaw, easy-bike, tempo/leguna) that generic vision models don't recognize — and produces a written report (PDF + Excel) suitable for handing to a client or stakeholder. Success is an accurate per-direction, per-vehicle-type count delivered as a professional document, without the operator needing to watch a raw terminal scroll by.

## Positioning

Combines a fast local motion-tracking pass (catches every crossing, including near-camera/off-angle traffic that a single mid-frame line would miss) with AI classification that only runs at the moment of a crossing — full accuracy without full-video-frame AI cost. Uses a Bangladesh-specific detection model so rickshaw/CNG/tempo are named correctly instead of falling into a generic "car/truck/bus" bucket the way a stock cloud vision API would.

## Constraints

- CPU-only inference on the operator's current machine (no confirmed GPU yet) — the tool includes an auto-speed mode that adapts classification detail to stay responsive on long/busy footage without ever skipping a vehicle crossing.
- The Bangladesh-specific detection model (BNVD) has no published license — for personal/local use, not redistributed.
- Runs as a local Flask server (`127.0.0.1`), not a hosted multi-tenant product — one operator, one job at a time is the expected usage pattern today.
- Video files can be large (hundreds of MB, up to ~1 hour); upload and processing both need to handle that without the page feeling broken or frozen.

## Terminology

- **Line / boundary box**: a user-placed virtual line (or 4-sided North/South/East/West box) the video is checked against; a vehicle "crossing" it is what gets counted.
- **In / Out**: direction of a crossing relative to a line's orientation.
- **Category**: the classified vehicle type (Car/Suv, Rickshaw, Auto, Motorcycle, Bus, Truck, etc.)
- **Auto-speed**: adaptive classification detail level (full / reduced / fast) the system picks automatically to keep up with a video's own pace.

## Accessibility

No stated requirement yet; build to reasonable default (keyboard-operable controls, sufficient contrast, readable at normal zoom).
