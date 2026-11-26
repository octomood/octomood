#!/usr/bin/env python3
"""Generate Material Design 3 Expressive SVG cards and GitHub Profile README.md.

Zero external dependencies: uses only Python standard library.
Generates paired Light & Dark SVGs for GitHub <picture> automatic theme switching.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "profile.config.json"
ASSETS_DIR = ROOT_DIR / "assets"
README_PATH = ROOT_DIR / "README.md"

FONT_SANS = (
    "'Inter', 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, "
    "Roboto, 'Helvetica Neue', Arial, sans-serif"
)
FONT_MONO = (
    "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, "
    "Menlo, Monaco, Consolas, monospace"
)

# Material Design 3 Expressive — Violet & Mint Tonal Palettes
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "surface": "#FEF7FF",
        "surfaceContainerLowest": "#FFFFFF",
        "surfaceContainerLow": "#F7F2FA",
        "surfaceContainer": "#F3EDF7",
        "surfaceContainerHigh": "#ECE6F0",
        "surfaceContainerHighest": "#E6E0E9",
        "primary": "#6750A4",
        "onPrimary": "#FFFFFF",
        "primaryContainer": "#EADDFF",
        "onPrimaryContainer": "#21005D",
        "secondary": "#006B5E",
        "onSecondary": "#FFFFFF",
        "secondaryContainer": "#9FFAE5",
        "onSecondaryContainer": "#00201B",
        "tertiary": "#7D5260",
        "onTertiary": "#FFFFFF",
        "tertiaryContainer": "#FFD8E4",
        "onTertiaryContainer": "#31111D",
        "onSurface": "#1D1B20",
        "onSurfaceVariant": "#49454F",
        "outline": "#79747E",
        "outlineVariant": "#CAC4D0",
        "heroGlowA": "#EADDFF",
        "heroGlowB": "#9FFAE5",
        "badgeBg": "#6750A4",
        "badgeFg": "#FFFFFF",
    },
    "dark": {
        "surface": "#141218",
        "surfaceContainerLowest": "#0F0D13",
        "surfaceContainerLow": "#1D1B20",
        "surfaceContainer": "#211F26",
        "surfaceContainerHigh": "#2B2930",
        "surfaceContainerHighest": "#36343B",
        "primary": "#D0BCFF",
        "onPrimary": "#381E72",
        "primaryContainer": "#4F378B",
        "onPrimaryContainer": "#EADDFF",
        "secondary": "#79F7DC",
        "onSecondary": "#00382F",
        "secondaryContainer": "#005046",
        "onSecondaryContainer": "#9FFAE5",
        "tertiary": "#EFB8C8",
        "onTertiary": "#492532",
        "tertiaryContainer": "#633B48",
        "onTertiaryContainer": "#FFD8E4",
        "onSurface": "#E6E0E9",
        "onSurfaceVariant": "#CAC4D0",
        "outline": "#938F99",
        "outlineVariant": "#49454F",
        "heroGlowA": "#4F378B",
        "heroGlowB": "#005046",
        "badgeBg": "#D0BCFF",
        "badgeFg": "#381E72",
    },
}


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def estimate_text_width(text: str, font_size: float, bold: bool = False, mono: bool = False) -> float:
    """Estimate proportional text width conservatively to prevent SVG clipping."""
    if mono:
        return len(text) * font_size * 0.62
    wide_chars = set("MWmw@#%&QGOD")
    narrow_chars = set("iljtfrI1!.,:;|' ")
    width = 0.0
    for ch in text:
        if ch in wide_chars:
            width += font_size * 0.80
        elif ch in narrow_chars:
            width += font_size * 0.34
        elif ch.isupper():
            width += font_size * 0.66
        else:
            width += font_size * 0.55
    if bold:
        width *= 1.05
    return width


def tone_colors(theme: dict[str, str], tone: str) -> tuple[str, str]:
    """Return (container_bg, on_container_fg) for an M3 tonal role."""
    mapping = {
        "primary": (theme["primaryContainer"], theme["onPrimaryContainer"]),
        "secondary": (theme["secondaryContainer"], theme["onSecondaryContainer"]),
        "tertiary": (theme["tertiaryContainer"], theme["onTertiaryContainer"]),
        "surface": (theme["surfaceContainerHigh"], theme["onSurface"]),
    }
    return mapping.get(tone, mapping["surface"])


def scalloped_cookie_path(cx: float, cy: float, r_base: float, amp: float, lobes: int = 10) -> str:
    """Create a smooth Material 3 Expressive scalloped flower/cookie SVG path."""
    steps = lobes * 16
    pts: list[tuple[float, float]] = []
    for i in range(steps):
        theta = (2.0 * math.pi * i) / steps
        r = r_base + amp * math.cos(lobes * theta)
        pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    # Smooth closed Catmull-Rom-to-Cubic-Bezier conversion
    n = len(pts)
    cmds = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        cmds.append(f"C {c1x:.2f} {c1y:.2f}, {c2x:.2f} {c2y:.2f}, {p2[0]:.2f} {p2[1]:.2f}")
    cmds.append("Z")
    return " ".join(cmds)


def clover_path(cx: float, cy: float, size: float) -> str:
    """Create a soft 4-lobe M3 Expressive clover shape."""
    return scalloped_cookie_path(cx, cy, r_base=size * 0.84, amp=size * 0.16, lobes=4)


def wavy_line_path(x_start: float, x_end: float, y_mid: float, amp: float = 3.5, wavelength: float = 24.0) -> str:
    """Create a smooth sinusoidal Material 3 Expressive wavy line path."""
    half_w = wavelength / 2.0
    x = x_start
    cmds = [f"M {x:.2f} {y_mid:.2f}"]
    direction = -1.0
    while x < x_end:
        nxt = min(x + half_w, x_end)
        seg_w = nxt - x
        ctrl_x = x + seg_w * 0.5
        ctrl_y = y_mid + direction * amp * 1.35 * (seg_w / half_w)
        cmds.append(f"Q {ctrl_x:.2f} {ctrl_y:.2f}, {nxt:.2f} {y_mid:.2f}")
        x = nxt
        direction *= -1.0
    return " ".join(cmds)


def render_icon(icon_name: str, x: float, y: float, size: float, color: str) -> str:
    """Render crisp 24x24-normalized Material-inspired vector icons."""
    scale = size / 24.0
    paths: dict[str, str] = {
        "shapes": (
            f'<path d="M12 3l4.5 7.5h-9L12 3z" fill="{color}"/>'
            f'<circle cx="17.5" cy="17.5" r="3.5" fill="{color}" opacity="0.88"/>'
            f'<rect x="3.5" y="14" width="6.5" height="6.5" rx="2" fill="{color}" opacity="0.72"/>'
        ),
        "terminal": (
            f'<rect x="3" y="4" width="18" height="16" rx="4" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<path d="M7.5 9.5l3 2.5-3 2.5M12.5 14.5h4" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
        "layers": (
            f'<path d="M12 3l8.5 4.5L12 12 3.5 7.5 12 3z" fill="{color}"/>'
            f'<path d="M3.5 12l8.5 4.5 8.5-4.5M3.5 16.5L12 21l8.5-4.5" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
        "sparkles": (
            f'<path d="M12 2l2.1 5.9L20 10l-5.9 2.1L12 18l-2.1-5.9L4 10l5.9-2.1L12 2z" fill="{color}"/>'
            f'<circle cx="19" cy="18.5" r="2" fill="{color}" opacity="0.8"/>'
        ),
        "github": (
            f'<path d="M12 2C6.48 2 2 6.58 2 12.23c0 4.52 2.87 8.35 6.84 9.7.5.1.68-.22.68-.49 0-.24-.01-1.04-.01-1.89-2.78.62-3.37-1.21-3.37-1.21-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.63.07-.63 1 .07 1.53 1.06 1.53 1.06.9 1.56 2.35 1.11 2.92.85.09-.66.35-1.11.63-1.36-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.27 2.75 1.05A9.38 9.38 0 0 1 12 6.84c.85 0 1.71.12 2.51.35 1.91-1.32 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.8-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.48-.01 2.81 0 .27.18.6.69.49A10.22 10.22 0 0 0 22 12.23C22 6.58 17.52 2 12 2z" fill="{color}"/>'
        ),
        "send": (
            f'<path d="M21 3L3 10.5l6.5 2.6L17 7.5l-5.6 7.5 6.6 5L21 3z" fill="{color}"/>'
        ),
        "briefcase": (
            f'<rect x="3" y="7" width="18" height="13" rx="3" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 12.5h18" fill="none" stroke="{color}" stroke-width="2"/>'
        ),
        "mail": (
            f'<rect x="3" y="5" width="18" height="14" rx="3" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<path d="M4.5 7l7.5 5.5L19.5 7" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
        "globe": (
            f'<circle cx="12" cy="12" r="9" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<ellipse cx="12" cy="12" rx="4" ry="9" fill="none" stroke="{color}" stroke-width="1.8"/>'
            f'<path d="M3.5 12h17" stroke="{color}" stroke-width="1.8"/>'
        ),
        "user": (
            f'<circle cx="12" cy="8" r="4" fill="{color}"/>'
            f'<path d="M4.5 20a7.5 7.5 0 0 1 15 0" fill="none" stroke="{color}" stroke-width="2.4" stroke-linecap="round"/>'
        ),
        "code": (
            f'<path d="M8.5 7.5L4 12l4.5 4.5M15.5 7.5L20 12l-4.5 4.5M13.5 5.5l-3 13" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
        "activity": (
            f'<path d="M3 12h4l2.5-6 4 12 2.5-6H21" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
    }
    body = paths.get(icon_name, paths["shapes"])
    return f'<g transform="translate({x:.2f}, {y:.2f}) scale({scale:.4f})">{body}</g>'


def svg_wrap(width: int, height: int, content: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" fill="none" role="img">\n'
        f"{content}\n"
        f"</svg>\n"
    )


def build_hero_svg(cfg: dict[str, Any], theme_name: str) -> str:
    t = THEMES[theme_name]
    w, h = 860, 276
    name = cfg.get("display_name", "Developer")
    role = cfg.get("role", "Software Engineer")
    tagline = cfg.get("tagline", "")
    status = cfg.get("status_pill", "AVAILABLE")
    monogram = cfg.get("monogram", "DV")
    pills: list[str] = cfg.get("hero_pills", [])

    # Decorative background M3 shapes
    cookie_big = scalloped_cookie_path(726, 138, r_base=82, amp=8.5, lobes=10)
    clover_mini = clover_path(612, 54, size=18)
    wavy = wavy_line_path(40, 220, 232, amp=3.0, wavelength=22.0)

    # Status pill width
    status_w = max(124.0, estimate_text_width(status, 11.5, bold=True, mono=True) + 38.0)

    # Hero bottom pills
    pill_svg = []
    px = 40.0
    py = 194.0
    pill_tones = ["primary", "secondary", "surface", "tertiary"]
    for idx, label in enumerate(pills[:4]):
        bg, fg = tone_colors(t, pill_tones[idx % len(pill_tones)])
        pw = estimate_text_width(label, 12.5, bold=True) + 28.0
        if px + pw > 590:
            break
        pill_svg.append(
            f'<rect x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="30" rx="15" fill="{bg}"/>'
            f'<text x="{px + pw / 2:.1f}" y="{py + 19.5:.1f}" text-anchor="middle" '
            f'font-family="{FONT_SANS}" font-size="12.5" font-weight="600" fill="{fg}">{esc(label)}</text>'
        )
        px += pw + 8.0

    # Subtle dot pattern in top-right corner
    dots = []
    for row in range(4):
        for col in range(5):
            dx = 560 + col * 14
            dy = 26 + row * 14
            dots.append(f'<circle cx="{dx}" cy="{dy}" r="1.5" fill="{t["primary"]}" opacity="0.18"/>')

    body = f"""
  <defs>
    <clipPath id="hero-clip">
      <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="32"/>
    </clipPath>
    <linearGradient id="hero-bg" x1="0" y1="0" x2="{w}" y2="{h}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{t['surfaceContainerLow']}"/>
      <stop offset="100%" stop-color="{t['surfaceContainer']}"/>
    </linearGradient>
    <linearGradient id="cookie-grad" x1="640" y1="50" x2="810" y2="230" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{t['primary']}"/>
      <stop offset="100%" stop-color="{t['secondary']}"/>
    </linearGradient>
  </defs>

  <g clip-path="url(#hero-clip)">
    <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="32" fill="url(#hero-bg)"/>
    <circle cx="775" cy="40" r="145" fill="{t['heroGlowA']}" opacity="0.55"/>
    <circle cx="670" cy="245" r="115" fill="{t['heroGlowB']}" opacity="0.48"/>
    <circle cx="90" cy="260" r="90" fill="{t['heroGlowA']}" opacity="0.22"/>
    {''.join(dots)}
    <path d="{clover_mini}" fill="{t['secondaryContainer']}" stroke="{t['secondary']}" stroke-opacity="0.3" stroke-width="1.5"/>
  </g>
  <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="32" stroke="{t['outlineVariant']}" stroke-width="1.5"/>

  <!-- Status Pill -->
  <rect x="40" y="34" width="{status_w:.1f}" height="28" rx="14" fill="{t['secondaryContainer']}"/>
  <circle cx="56" cy="48" r="4" fill="{t['secondary']}"/>
  <text x="67" y="52" font-family="{FONT_MONO}" font-size="11.5" font-weight="700" letter-spacing="0.6" fill="{t['onSecondaryContainer']}">{esc(status)}</text>

  <!-- Display Name & Subtitle -->
  <text x="40" y="106" font-family="{FONT_SANS}" font-size="38" font-weight="800" letter-spacing="-0.8" fill="{t['onSurface']}">Hey, I'm {esc(name)}</text>
  <text x="40" y="138" font-family="{FONT_SANS}" font-size="18" font-weight="600" fill="{t['primary']}">{esc(role)}</text>
  <text x="40" y="166" font-family="{FONT_SANS}" font-size="14" font-weight="400" fill="{t['onSurfaceVariant']}">{esc(tagline)}</text>

  <!-- Expressive Hero Pills -->
  {''.join(pill_svg)}

  <!-- Subtle Wavy Accent -->
  <path d="{wavy}" stroke="{t['secondary']}" stroke-width="2.5" stroke-linecap="round" opacity="0.65"/>

  <!-- Right Side MD3 Expressive Cookie Badge -->
  <path d="{cookie_big}" fill="url(#cookie-grad)" opacity="0.16" transform="translate(8, 8)"/>
  <path d="{cookie_big}" fill="{t['primaryContainer']}" stroke="{t['primary']}" stroke-opacity="0.38" stroke-width="2"/>
  <circle cx="726" cy="138" r="54" fill="{t['surfaceContainerLowest']}" stroke="{t['outlineVariant']}" stroke-width="1.2"/>
  <text x="726" y="151" text-anchor="middle" font-family="{FONT_SANS}" font-size="34" font-weight="800" letter-spacing="-1" fill="{t['primary']}">{esc(monogram)}</text>

  <!-- Floating Sticker Pill -->
  <rect x="668" y="216" width="116" height="28" rx="14" fill="{t['badgeBg']}"/>
  <text x="726" y="234" text-anchor="middle" font-family="{FONT_MONO}" font-size="11" font-weight="700" letter-spacing="0.5" fill="{t['badgeFg']}">MD3 EXPRESSIVE</text>
"""
    return svg_wrap(w, h, body)


def build_about_stack_svg(cfg: dict[str, Any], theme_name: str) -> str:
    t = THEMES[theme_name]
    w, h = 860, 290
    gap = 16
    left_w = 396
    right_x = left_w + gap
    right_w = w - right_x

    about = cfg.get("about", {})
    stack = cfg.get("stack", {})

    # About bio lines
    bio_lines_svg = []
    for idx, line in enumerate(about.get("bio_lines", [])[:3]):
        bio_lines_svg.append(
            f'<text x="28" y="{94 + idx * 22}" font-family="{FONT_SANS}" font-size="14" fill="{t["onSurfaceVariant"]}">{esc(line)}</text>'
        )

    # About highlight rows
    highlights_svg = []
    hy = 172
    for idx, item in enumerate(about.get("highlights", [])[:3]):
        lbl = item.get("label", "")
        val = item.get("value", "")
        lbl_w = max(78.0, estimate_text_width(lbl, 11.5, bold=True) + 20.0)
        bg, fg = tone_colors(t, ["primary", "secondary", "tertiary"][idx % 3])
        highlights_svg.append(
            f'<rect x="28" y="{hy}" width="{lbl_w:.1f}" height="26" rx="13" fill="{bg}"/>'
            f'<text x="{28 + lbl_w / 2:.1f}" y="{hy + 17:.1f}" text-anchor="middle" font-family="{FONT_SANS}" font-size="11.5" font-weight="700" fill="{fg}">{esc(lbl)}</text>'
            f'<text x="{28 + lbl_w + 12:.1f}" y="{hy + 17.5:.1f}" font-family="{FONT_SANS}" font-size="13.5" font-weight="500" fill="{t["onSurface"]}">{esc(val)}</text>'
        )
        hy += 34

    # Tech stack wrapping pill chips
    chips_svg = []
    cx = right_x + 28.0
    cy = 104.0
    max_x = w - 28.0
    chip_h = 34.0
    chip_gap_x = 10.0
    chip_gap_y = 12.0

    for item in stack.get("items", []):
        label = item.get("name", "")
        tone = item.get("tone", "surface")
        bg, fg = tone_colors(t, tone)
        cw = estimate_text_width(label, 13.0, bold=True) + 30.0
        if cx + cw > max_x:
            cx = right_x + 28.0
            cy += chip_h + chip_gap_y
        if cy + chip_h > h - 22:
            break
        border = f' stroke="{t["outlineVariant"]}" stroke-width="1"' if tone == "surface" else ""
        chips_svg.append(
            f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cw:.1f}" height="{chip_h:.1f}" rx="17" fill="{bg}"{border}/>'
            f'<text x="{cx + cw / 2:.1f}" y="{cy + 21.5:.1f}" text-anchor="middle" font-family="{FONT_SANS}" font-size="13" font-weight="600" fill="{fg}">{esc(label)}</text>'
        )
        cx += cw + chip_gap_x

    body = f"""
  <!-- Left Bento: About Me -->
  <rect x="1" y="1" width="{left_w - 2}" height="{h - 2}" rx="28" fill="{t['surfaceContainerLow']}" stroke="{t['outlineVariant']}" stroke-width="1.5"/>
  <rect x="28" y="26" width="36" height="36" rx="12" fill="{t['primaryContainer']}"/>
  {render_icon("user", 36, 34, 20, t["onPrimaryContainer"])}
  <text x="76" y="49" font-family="{FONT_SANS}" font-size="19" font-weight="700" fill="{t['onSurface']}">{esc(about.get("title", "About Me"))}</text>
  {''.join(bio_lines_svg)}
  <line x1="28" y1="156" x2="{left_w - 28}" y2="156" stroke="{t['outlineVariant']}" stroke-width="1" stroke-dasharray="4 4"/>
  {''.join(highlights_svg)}

  <!-- Right Bento: Tech Stack -->
  <rect x="{right_x + 1}" y="1" width="{right_w - 2}" height="{h - 2}" rx="28" fill="{t['surfaceContainerLow']}" stroke="{t['outlineVariant']}" stroke-width="1.5"/>
  <rect x="{right_x + 28}" y="26" width="36" height="36" rx="12" fill="{t['secondaryContainer']}"/>
  {render_icon("code", right_x + 36, 34, 20, t["onSecondaryContainer"])}
  <text x="{right_x + 76}" y="44" font-family="{FONT_SANS}" font-size="19" font-weight="700" fill="{t['onSurface']}">{esc(stack.get("title", "Tech Stack"))}</text>
  <text x="{right_x + 76}" y="62" font-family="{FONT_SANS}" font-size="12.5" font-weight="500" fill="{t['onSurfaceVariant']}">{esc(stack.get("subtitle", ""))}</text>
  {''.join(chips_svg)}
"""
    return svg_wrap(w, h, body)


def build_project_svg(project: dict[str, Any], theme_name: str) -> str:
    t = THEMES[theme_name]
    w, h = 422, 184
    name = project.get("name", "Project")
    tag = project.get("tag", "Project")
    desc = project.get("description", ["", ""])
    lang = project.get("language", "TypeScript")
    lang_color = project.get("lang_color", t["primary"])
    badge = project.get("badge", "Open Source")
    icon_name = project.get("icon", "shapes")
    tone = project.get("tone", "primary")

    icon_bg, icon_fg = tone_colors(t, tone)
    tag_w = estimate_text_width(tag, 11.5, bold=True) + 22.0
    badge_w = estimate_text_width(badge, 11.0, bold=True, mono=True) + 20.0
    clover = clover_path(386, 152, size=52)

    body = f"""
  <defs>
    <clipPath id="proj-clip">
      <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="28"/>
    </clipPath>
  </defs>
  <g clip-path="url(#proj-clip)">
    <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="28" fill="{t['surfaceContainerLow']}"/>
    <path d="{clover}" fill="{icon_bg}" opacity="0.45"/>
  </g>
  <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="28" stroke="{t['outlineVariant']}" stroke-width="1.5"/>

  <!-- Icon Squircle & Title -->
  <rect x="24" y="22" width="42" height="42" rx="14" fill="{icon_bg}"/>
  {render_icon(icon_name, 33, 31, 24, icon_fg)}
  <text x="78" y="42" font-family="{FONT_SANS}" font-size="18.5" font-weight="700" fill="{t['onSurface']}">{esc(name)}</text>
  <rect x="78" y="49" width="{tag_w:.1f}" height="22" rx="11" fill="{t['surfaceContainerHigh']}"/>
  <text x="{78 + tag_w / 2:.1f}" y="63.5" text-anchor="middle" font-family="{FONT_SANS}" font-size="11.5" font-weight="600" fill="{t['onSurfaceVariant']}">{esc(tag)}</text>

  <!-- Open Link Pill -->
  <circle cx="384" cy="39" r="16" fill="{t['surfaceContainerHigh']}"/>
  <path d="M379 44l10-10M381 34h8v8" fill="none" stroke="{t['primary']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>

  <!-- Description -->
  <text x="24" y="102" font-family="{FONT_SANS}" font-size="13.8" fill="{t['onSurfaceVariant']}">{esc(desc[0] if len(desc) > 0 else "")}</text>
  <text x="24" y="122" font-family="{FONT_SANS}" font-size="13.8" fill="{t['onSurfaceVariant']}">{esc(desc[1] if len(desc) > 1 else "")}</text>

  <!-- Bottom Meta Row -->
  <circle cx="31" cy="153" r="5.5" fill="{esc(lang_color)}"/>
  <text x="44" y="157.5" font-family="{FONT_SANS}" font-size="13" font-weight="600" fill="{t['onSurface']}">{esc(lang)}</text>

  <rect x="{w - 24 - badge_w:.1f}" y="140" width="{badge_w:.1f}" height="24" rx="12" fill="{icon_bg}"/>
  <text x="{w - 24 - badge_w / 2:.1f}" y="155.5" text-anchor="middle" font-family="{FONT_MONO}" font-size="11" font-weight="700" fill="{icon_fg}">{esc(badge)}</text>
"""
    return svg_wrap(w, h, body)


def build_stats_svg(cfg: dict[str, Any], theme_name: str) -> str:
    t = THEMES[theme_name]
    w, h = 860, 232
    gap = 16
    left_w = 432
    right_x = left_w + gap
    right_w = w - right_x

    stats = cfg.get("stats", {})
    metrics = [
        ("Commits / Year", stats.get("contributions", "1,000+"), "primary"),
        ("Repositories", stats.get("repos", "25"), "secondary"),
        ("Public Stars", stats.get("stars", "200"), "tertiary"),
        ("Followers", stats.get("followers", "100"), "surface"),
    ]

    # 2x2 mini stat pills inside left card
    tiles_svg = []
    tile_w = 182
    tile_h = 54
    for idx, (label, val, tone) in enumerate(metrics):
        col = idx % 2
        row = idx // 2
        tx = 24 + col * (tile_w + 14)
        ty = 84 + row * (tile_h + 12)
        bg, fg = tone_colors(t, tone)
        border = f' stroke="{t["outlineVariant"]}" stroke-width="1"' if tone == "surface" else ""
        tiles_svg.append(
            f'<rect x="{tx}" y="{ty}" width="{tile_w}" height="{tile_h}" rx="18" fill="{bg}"{border}/>'
            f'<text x="{tx + 16}" y="{ty + 23}" font-family="{FONT_SANS}" font-size="11.5" font-weight="600" fill="{fg}" opacity="0.85">{esc(label)}</text>'
            f'<text x="{tx + 16}" y="{ty + 43}" font-family="{FONT_SANS}" font-size="18.5" font-weight="800" fill="{fg}">{esc(val)}</text>'
        )

    # Right Bento: Top Languages with MD3 Segmented Capsule + Wavy indicator
    langs: list[dict[str, Any]] = stats.get("languages", [])
    total_pct = sum(float(l.get("percent", 0)) for l in langs) or 100.0
    bar_x = right_x + 26.0
    bar_y = 88.0
    bar_w = right_w - 52.0
    bar_h = 16.0
    seg_gap = 4.0
    usable_w = bar_w - seg_gap * max(0, len(langs) - 1)

    bars_svg = []
    legend_svg = []
    cur_x = bar_x
    for idx, lang in enumerate(langs[:4]):
        pct = float(lang.get("percent", 0))
        seg_w = max(16.0, usable_w * (pct / total_pct))
        c = lang.get(f"color_{theme_name}", t["primary"])
        bars_svg.append(
            f'<rect x="{cur_x:.1f}" y="{bar_y:.1f}" width="{seg_w:.1f}" height="{bar_h:.1f}" rx="8" fill="{esc(c)}"/>'
        )
        cur_x += seg_w + seg_gap

        col = idx % 2
        row = idx // 2
        lx = right_x + 26 + col * 184
        ly = 132 + row * 34
        legend_svg.append(
            f'<rect x="{lx}" y="{ly}" width="168" height="26" rx="13" fill="{t["surfaceContainerHigh"]}"/>'
            f'<circle cx="{lx + 14}" cy="{ly + 13}" r="5" fill="{esc(c)}"/>'
            f'<text x="{lx + 26}" y="{ly + 17}" font-family="{FONT_SANS}" font-size="12.5" font-weight="600" fill="{t["onSurface"]}">{esc(lang.get("name", ""))}</text>'
            f'<text x="{lx + 154}" y="{ly + 17}" text-anchor="end" font-family="{FONT_MONO}" font-size="11.5" font-weight="700" fill="{t["onSurfaceVariant"]}">{int(round(pct))}%</text>'
        )

    wavy = wavy_line_path(right_x + 26, w - 26, 206, amp=3.0, wavelength=22.0)

    body = f"""
  <!-- Left Bento: GitHub Snapshot -->
  <rect x="1" y="1" width="{left_w - 2}" height="{h - 2}" rx="28" fill="{t['surfaceContainerLow']}" stroke="{t['outlineVariant']}" stroke-width="1.5"/>
  <rect x="24" y="24" width="36" height="36" rx="12" fill="{t['primaryContainer']}"/>
  {render_icon("activity", 32, 32, 20, t["onPrimaryContainer"])}
  <text x="72" y="47" font-family="{FONT_SANS}" font-size="19" font-weight="700" fill="{t['onSurface']}">{esc(stats.get("title", "GitHub Snapshot"))}</text>
  {''.join(tiles_svg)}

  <!-- Right Bento: Languages -->
  <rect x="{right_x + 1}" y="1" width="{right_w - 2}" height="{h - 2}" rx="28" fill="{t['surfaceContainerLow']}" stroke="{t['outlineVariant']}" stroke-width="1.5"/>
  <rect x="{right_x + 26}" y="24" width="36" height="36" rx="12" fill="{t['secondaryContainer']}"/>
  {render_icon("layers", right_x + 34, 32, 20, t["onSecondaryContainer"])}
  <text x="{right_x + 74}" y="47" font-family="{FONT_SANS}" font-size="19" font-weight="700" fill="{t['onSurface']}">{esc(stats.get("languages_title", "Top Languages"))}</text>
  {''.join(bars_svg)}
  {''.join(legend_svg)}
  <path d="{wavy}" stroke="{t['primary']}" stroke-width="2.2" stroke-linecap="round" opacity="0.5"/>
"""
    return svg_wrap(w, h, body)


def social_pill_width(count: int) -> int:
    if count <= 0:
        return 204
    if count <= 3:
        return (860 - (count - 1) * 16) // count
    return 204


def build_social_pill_svg(social: dict[str, Any], theme_name: str, width: int = 204) -> str:
    t = THEMES[theme_name]
    w, h = width, 58
    label = social.get("label", "Link")
    handle = social.get("handle", "")
    icon_name = social.get("icon", "globe")
    tone = social.get("tone", "surface")
    bg, fg = tone_colors(t, tone)
    border = f' stroke="{t["outlineVariant"]}" stroke-width="1.5"' if tone == "surface" else ""

    body = f"""
  <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="28" fill="{bg}"{border}/>
  <circle cx="29" cy="29" r="17" fill="{t['surfaceContainerLowest']}" opacity="0.88"/>
  {render_icon(icon_name, 19, 19, 20, t['primary'] if tone == 'surface' else fg)}
  <text x="56" y="25.5" font-family="{FONT_SANS}" font-size="13.5" font-weight="700" fill="{fg}">{esc(label)}</text>
  <text x="56" y="42" font-family="{FONT_MONO}" font-size="11" font-weight="500" fill="{fg}" opacity="0.82">{esc(handle)}</text>
"""
    return svg_wrap(w, h, body)


def build_footer_svg(cfg: dict[str, Any], theme_name: str) -> str:
    t = THEMES[theme_name]
    w, h = 860, 62
    wavy_left = wavy_line_path(20, 290, 31, amp=3.5, wavelength=26.0)
    wavy_right = wavy_line_path(570, 840, 31, amp=3.5, wavelength=26.0)
    text = f"MATERIAL 3 EXPRESSIVE • @{cfg.get('github_username', 'profile').upper()}"
    pill_w = max(230.0, estimate_text_width(text, 11.0, bold=True, mono=True) + 34.0)
    px = (w - pill_w) / 2.0

    body = f"""
  <path d="{wavy_left}" stroke="{t['primary']}" stroke-width="2.2" stroke-linecap="round" opacity="0.45"/>
  <path d="{wavy_right}" stroke="{t['secondary']}" stroke-width="2.2" stroke-linecap="round" opacity="0.55"/>
  <rect x="{px:.1f}" y="16" width="{pill_w:.1f}" height="30" rx="15" fill="{t['surfaceContainerHigh']}" stroke="{t['outlineVariant']}" stroke-width="1"/>
  <text x="{w / 2:.1f}" y="35" text-anchor="middle" font-family="{FONT_MONO}" font-size="11" font-weight="700" letter-spacing="0.5" fill="{t['onSurfaceVariant']}">{esc(text)}</text>
"""
    return svg_wrap(w, h, body)


def picture_tag(base_name: str, alt: str, width: str = "100%") -> str:
    return (
        f'<picture>\n'
        f'    <source media="(prefers-color-scheme: dark)" srcset="./assets/{base_name}-dark.svg" />\n'
        f'    <source media="(prefers-color-scheme: light)" srcset="./assets/{base_name}-light.svg" />\n'
        f'    <img alt="{esc(alt)}" src="./assets/{base_name}-light.svg" width="{width}" />\n'
        f'  </picture>'
    )


def build_readme(cfg: dict[str, Any]) -> str:
    name = cfg.get("display_name", "Developer")
    projects: list[dict[str, Any]] = cfg.get("projects", [])
    socials: list[dict[str, Any]] = cfg.get("socials", [])

    # 2x2 clickable project grid without HTML table borders
    project_rows = []
    for i in range(0, len(projects), 2):
        row_items = []
        for offset in range(2):
            idx = i + offset
            if idx >= len(projects):
                break
            proj = projects[idx]
            url = esc(proj.get("url", "#"))
            pname = esc(proj.get("name", f"Project {idx + 1}"))
            row_items.append(
                f'  <a href="{url}">\n'
                f'    {picture_tag(f"project-{idx + 1}", pname, width="420")}\n'
                f'  </a>'
            )
        project_rows.append('<p align="center">\n' + "\n  &nbsp;\n".join(row_items) + "\n</p>")

    soc_w = social_pill_width(len(socials))
    social_links = []
    for idx, soc in enumerate(socials):
        url = esc(soc.get("url", "#"))
        lbl = esc(soc.get("label", f"Social {idx + 1}"))
        social_links.append(
            f'  <a href="{url}">\n'
            f'    {picture_tag(f"social-{idx + 1}", lbl, width=str(soc_w))}\n'
            f'  </a>'
        )

    sections = [
        f'<p align="center">\n  {picture_tag("hero", f"{name} — Material 3 Expressive Header", width="860")}\n</p>',
        f'<p align="center">\n  {picture_tag("about-stack", "About Me & Tech Stack", width="860")}\n</p>',
        "\n".join(project_rows),
        f'<p align="center">\n  {picture_tag("stats", "GitHub Snapshot & Top Languages", width="860")}\n</p>',
        '<p align="center">\n' + "\n  &nbsp;\n".join(social_links) + "\n</p>",
        f'<p align="center">\n  {picture_tag("footer", "Material 3 Expressive Footer", width="860")}\n</p>',
    ]
    return "\n\n".join(sections) + "\n"


def fetch_github_stats(username: str) -> dict[str, Any]:
    """Fetch public GitHub profile & repository statistics using GitHub REST API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "md3-expressive-readme-generator",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def get_json(url: str) -> Any:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    user = get_json(f"https://api.github.com/users/{username}")
    repos = get_json(f"https://api.github.com/users/{username}/repos?per_page=100&type=owner")

    total_stars = sum(int(r.get("stargazers_count", 0)) for r in repos if not r.get("fork"))
    lang_bytes: dict[str, int] = {}
    for r in repos:
        if r.get("fork"):
            continue
        langs_url = r.get("languages_url")
        if langs_url:
            repo_langs = get_json(langs_url)
            for lname, lbytes in repo_langs.items():
                lang_bytes[lname] = lang_bytes.get(lname, 0) + int(lbytes)

    top_sorted = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)[:4]
    total_lang = sum(v for _, v in top_sorted) or 1
    palette_pairs = [
        ("#6750A4", "#D0BCFF"),
        ("#006B5E", "#79F7DC"),
        ("#4A5CC8", "#B6C4FF"),
        ("#8E4A75", "#F2B8DA"),
    ]
    languages = []
    for idx, (lname, lval) in enumerate(top_sorted):
        cl, cd = palette_pairs[idx % len(palette_pairs)]
        languages.append(
            {
                "name": lname,
                "percent": max(1, round((lval / total_lang) * 100)),
                "color_light": cl,
                "color_dark": cd,
            }
        )

    return {
        "repos": str(user.get("public_repos", len(repos))),
        "stars": str(total_stars),
        "followers": str(user.get("followers", 0)),
        "languages": languages,
    }


def generate_all(cfg: dict[str, Any]) -> list[Path]:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    socials = cfg.get("socials", [])
    soc_w = social_pill_width(len(socials))

    # Remove stale social SVGs if count changed
    for old_soc in ASSETS_DIR.glob("social-*.svg"):
        old_soc.unlink()

    for theme_name in ("light", "dark"):
        files = {
            f"hero-{theme_name}.svg": build_hero_svg(cfg, theme_name),
            f"about-stack-{theme_name}.svg": build_about_stack_svg(cfg, theme_name),
            f"stats-{theme_name}.svg": build_stats_svg(cfg, theme_name),
            f"footer-{theme_name}.svg": build_footer_svg(cfg, theme_name),
        }
        for idx, proj in enumerate(cfg.get("projects", []), start=1):
            files[f"project-{idx}-{theme_name}.svg"] = build_project_svg(proj, theme_name)
        for idx, soc in enumerate(socials, start=1):
            files[f"social-{idx}-{theme_name}.svg"] = build_social_pill_svg(soc, theme_name, width=soc_w)

        for fname, content in files.items():
            out_path = ASSETS_DIR / fname
            out_path.write_text(content, encoding="utf-8")
            written.append(out_path)

    README_PATH.write_text(build_readme(cfg), encoding="utf-8")
    written.append(README_PATH)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MD3 Expressive GitHub Profile README & SVGs.")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="Path to profile.config.json")
    parser.add_argument(
        "--fetch-github",
        action="store_true",
        help="Fetch live repos, stars, followers, and languages from GitHub API",
    )
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))

    if args.fetch_github:
        username = cfg.get("github_username", "")
        if not username:
            raise SystemExit("github_username is empty in config")
        try:
            live = fetch_github_stats(username)
            cfg.setdefault("stats", {}).update(
                {
                    "repos": live["repos"],
                    "stars": live["stars"],
                    "followers": live["followers"],
                }
            )
            if live["languages"]:
                cfg["stats"]["languages"] = live["languages"]
            args.config.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            print(f"Updated stats from GitHub API for @{username}")
        except urllib.error.URLError as exc:
            print(f"Warning: could not fetch GitHub stats ({exc}); using existing config values.")

    written = generate_all(cfg)
    print(f"Generated {len(written)} files in {ROOT_DIR}")


if __name__ == "__main__":
    main()
