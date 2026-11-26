#!/usr/bin/env python3
"""Generate animated Material Design 3 Expressive SVG cards and GitHub Profile README.md.

Zero external dependencies: uses only Python standard library.
- Borderless M3 tonal Surface Containers (m3.material.io aesthetic)
- Embedded base64 avatar inside an animated rotating M3 scalloped frame
- Smooth SVG SMIL + CSS animations compatible with GitHub's <img> SVG sandbox
- Percentage widths in README.md so 2 projects & 3 contact pills stay side-by-side
"""

from __future__ import annotations

import argparse
import base64
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
    "'Google Sans', 'Inter', 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, "
    "Roboto, 'Helvetica Neue', Arial, sans-serif"
)

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "surface": "#FEF7FF",
        "surfaceContainerLowest": "#FFFFFF",
        "surfaceContainerLow": "#F7F2FA",
        "surfaceContainer": "#F3EDF7",
        "surfaceContainerHigh": "#EAE3F2",
        "surfaceContainerHighest": "#E4DCEB",
        "primary": "#6750A4",
        "onPrimary": "#FFFFFF",
        "primaryContainer": "#EADDFF",
        "onPrimaryContainer": "#21005D",
        "secondary": "#006B5E",
        "onSecondary": "#FFFFFF",
        "secondaryContainer": "#B8F3E5",
        "onSecondaryContainer": "#00201B",
        "tertiary": "#7D5260",
        "onTertiary": "#FFFFFF",
        "tertiaryContainer": "#FFD8E4",
        "onTertiaryContainer": "#31111D",
        "onSurface": "#1D1B20",
        "onSurfaceVariant": "#49454F",
        "heroShapeA": "#D0BCFF",
        "heroShapeB": "#8FE8D4",
        "heroShapeC": "#F6C8D8",
    },
    "dark": {
        "surface": "#141218",
        "surfaceContainerLowest": "#0F0D13",
        "surfaceContainerLow": "#1D1B20",
        "surfaceContainer": "#221F27",
        "surfaceContainerHigh": "#2D2A34",
        "surfaceContainerHighest": "#373340",
        "primary": "#D0BCFF",
        "onPrimary": "#381E72",
        "primaryContainer": "#4F378B",
        "onPrimaryContainer": "#EADDFF",
        "secondary": "#7ADBC8",
        "onSecondary": "#00382F",
        "secondaryContainer": "#134D44",
        "onSecondaryContainer": "#B8F3E5",
        "tertiary": "#EFB8C8",
        "onTertiary": "#492532",
        "tertiaryContainer": "#633B48",
        "onTertiaryContainer": "#FFD8E4",
        "onSurface": "#E6E0E9",
        "onSurfaceVariant": "#CAC4D0",
        "heroShapeA": "#4F378B",
        "heroShapeB": "#134D44",
        "heroShapeC": "#633B48",
    },
}


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def estimate_text_width(text: str, font_size: float, bold: bool = False) -> float:
    wide_chars = set("MWmw@#%&QGOD")
    narrow_chars = set("iljtfrI1!.,:;|' ")
    width = 0.0
    for ch in text:
        if ch in wide_chars:
            width += font_size * 0.78
        elif ch in narrow_chars:
            width += font_size * 0.34
        elif ch.isupper():
            width += font_size * 0.65
        else:
            width += font_size * 0.54
    if bold:
        width *= 1.04
    return width


def tone_colors(theme: dict[str, str], tone: str) -> tuple[str, str]:
    mapping = {
        "primary": (theme["primaryContainer"], theme["onPrimaryContainer"]),
        "secondary": (theme["secondaryContainer"], theme["onSecondaryContainer"]),
        "tertiary": (theme["tertiaryContainer"], theme["onTertiaryContainer"]),
        "surface": (theme["surfaceContainerHigh"], theme["onSurface"]),
    }
    return mapping.get(tone, mapping["surface"])


def scalloped_path(cx: float, cy: float, r_base: float, amp: float, lobes: int = 12) -> str:
    """Create a smooth Material 3 Expressive scalloped flower/cookie shape."""
    steps = lobes * 16
    pts: list[tuple[float, float]] = []
    for i in range(steps):
        theta = (2.0 * math.pi * i) / steps
        r = r_base + amp * math.cos(lobes * theta)
        pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
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


def four_point_star_path(cx: float, cy: float, r_outer: float, r_inner: float) -> str:
    pts: list[tuple[float, float]] = []
    for i in range(8):
        angle = i * math.pi / 4.0 - math.pi / 2.0
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    cmds = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for i in range(8):
        curr = pts[i]
        nxt = pts[(i + 1) % 8]
        mid_x = (curr[0] + nxt[0]) * 0.5
        mid_y = (curr[1] + nxt[1]) * 0.5
        ctrl_x = mid_x * 0.85 + cx * 0.15
        ctrl_y = mid_y * 0.85 + cy * 0.15
        cmds.append(f"Q {ctrl_x:.2f} {ctrl_y:.2f}, {nxt[0]:.2f} {nxt[1]:.2f}")
    cmds.append("Z")
    return " ".join(cmds)


def wavy_line_path(x_start: float, x_end: float, y_mid: float, amp: float = 4.0, wavelength: float = 28.0) -> str:
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
    scale = size / 24.0
    paths: dict[str, str] = {
        "github": (
            f'<path d="M12 2C6.48 2 2 6.58 2 12.23c0 4.52 2.87 8.35 6.84 9.7.5.1.68-.22.68-.49 0-.24-.01-1.04-.01-1.89-2.78.62-3.37-1.21-3.37-1.21-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.63.07-.63 1 .07 1.53 1.06 1.53 1.06.9 1.56 2.35 1.11 2.92.85.09-.66.35-1.11.63-1.36-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.27 2.75 1.05A9.38 9.38 0 0 1 12 6.84c.85 0 1.71.12 2.51.35 1.91-1.32 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.8-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.48-.01 2.81 0 .27.18.6.69.49A10.22 10.22 0 0 0 22 12.23C22 6.58 17.52 2 12 2z" fill="{color}"/>'
        ),
        "send": (
            f'<path d="M21 3L3 10.5l6.5 2.6L17 7.5l-5.6 7.5 6.6 5L21 3z" fill="{color}"/>'
        ),
        "sparkles": (
            f'<path d="M12 2l2.2 6.2L20.5 10.5l-6.3 2.3L12 19l-2.2-6.2L3.5 10.5l6.3-2.3L12 2z" fill="{color}"/>'
        ),
        "code": (
            f'<path d="M8.5 7.5L4 12l4.5 4.5M15.5 7.5L20 12l-4.5 4.5M13.5 5.5l-3 13" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
        "user": (
            f'<circle cx="12" cy="8" r="4" fill="{color}"/>'
            f'<path d="M4.5 20a7.5 7.5 0 0 1 15 0" fill="none" stroke="{color}" stroke-width="2.4" stroke-linecap="round"/>'
        ),
        "activity": (
            f'<path d="M3 12h4l2.5-6 4 12 2.5-6H21" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
        "layers": (
            f'<path d="M12 3l8.5 4.5L12 12 3.5 7.5 12 3z" fill="{color}"/>'
            f'<path d="M3.5 12l8.5 4.5 8.5-4.5M3.5 16.5L12 21l8.5-4.5" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        ),
    }
    body = paths.get(icon_name, paths["sparkles"])
    return f'<g transform="translate({x:.2f}, {y:.2f}) scale({scale:.4f})">{body}</g>'


def svg_wrap(width: int, height: int, content: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" role="img">\n'
        f"{content}\n"
        f"</svg>\n"
    )


def load_avatar_data_uri(cfg: dict[str, Any]) -> str | None:
    rel = cfg.get("avatar_path")
    if not rel:
        return None
    p = ROOT_DIR / rel
    if not p.is_file():
        return None
    raw = p.read_bytes()
    ext = p.suffix.lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_hero_svg(cfg: dict[str, Any], theme_name: str) -> str:
    t = THEMES[theme_name]
    w, h = 860, 268
    name = cfg.get("display_name", "churros")
    role = cfg.get("role", "Desktop, Web & Bot Developer")
    alt_role = cfg.get("alt_role", "Creator of TikTok Octo & OctoLoad")
    monogram = cfg.get("monogram", "CH")
    chips = cfg.get("hero_chips", [])

    # Left avatar scalloped frame (animated rotation) + stationary scalloped avatar inside
    ax, ay = 128.0, 134.0
    outer_scallop = scalloped_path(ax, ay, r_base=82, amp=8.5, lobes=12)
    inner_scallop = scalloped_path(ax, ay, r_base=69, amp=5.5, lobes=12)
    avatar_uri = load_avatar_data_uri(cfg)

    if avatar_uri:
        avatar_inner = (
            f'<image x="{ax - 76:.1f}" y="{ay - 76:.1f}" width="152" height="152" '
            f'preserveAspectRatio="xMidYMid slice" href="{avatar_uri}" xlink:href="{avatar_uri}"/>'
        )
    else:
        avatar_inner = (
            f'<rect x="{ax - 76:.1f}" y="{ay - 76:.1f}" width="152" height="152" fill="{t["primaryContainer"]}"/>'
            f'<text x="{ax:.1f}" y="{ay + 14:.1f}" text-anchor="middle" font-family="{FONT_SANS}" '
            f'font-size="40" font-weight="800" fill="{t["onPrimaryContainer"]}">{esc(monogram)}</text>'
        )

    # Right decorative animated M3 Expressive shapes (like m3.material.io)
    right_blob = scalloped_path(788, 66, r_base=74, amp=16.0, lobes=6)
    right_clover = scalloped_path(732, 214, r_base=36, amp=8.0, lobes=4)
    right_gear = scalloped_path(816, 174, r_base=24, amp=4.0, lobes=8)
    spark = four_point_star_path(698, 44, r_outer=14, r_inner=4.5)

    # Subtitle cursor position
    role_w = estimate_text_width(role, 17.5, bold=False)
    caret_x = 248.0 + role_w + 5.0

    # Chips below subtitle
    chips_svg = []
    cx = 248.0
    cy = 186.0
    for item in chips[:3]:
        lbl = item.get("label", "")
        icon_name = item.get("icon", "sparkles")
        tone = item.get("tone", "primary")
        bg, fg = tone_colors(t, tone)
        cw = estimate_text_width(lbl, 13.5, bold=True) + 46.0
        chips_svg.append(
            f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cw:.1f}" height="34" rx="17" fill="{bg}"/>'
            f'{render_icon(icon_name, cx + 12, cy + 8.5, 17, fg)}'
            f'<text x="{cx + 35:.1f}" y="{cy + 21.5:.1f}" font-family="{FONT_SANS}" font-size="13.5" font-weight="600" fill="{fg}">{esc(lbl)}</text>'
        )
        cx += cw + 10.0

    body = f"""
  <defs>
    <clipPath id="hero-clip">
      <rect x="0" y="0" width="{w}" height="{h}" rx="34"/>
    </clipPath>
    <clipPath id="avatar-scallop-clip">
      <path d="{inner_scallop}"/>
    </clipPath>
    <style>
      .role-a {{
        animation: swapA 9s ease-in-out infinite;
      }}
      .role-b {{
        animation: swapB 9s ease-in-out infinite;
      }}
      .caret {{
        animation: blink 1s steps(2, start) infinite;
      }}
      @keyframes swapA {{
        0%, 44% {{ opacity: 1; }}
        50%, 94% {{ opacity: 0; }}
        100% {{ opacity: 1; }}
      }}
      @keyframes swapB {{
        0%, 44% {{ opacity: 0; }}
        50%, 94% {{ opacity: 1; }}
        100% {{ opacity: 0; }}
      }}
      @keyframes blink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
    </style>
  </defs>

  <g clip-path="url(#hero-clip)">
    <!-- Borderless M3 Surface Container -->
    <rect x="0" y="0" width="{w}" height="{h}" rx="34" fill="{t['surfaceContainer']}"/>

    <!-- Animated M3 Expressive Right Shapes -->
    <g opacity="0.72">
      <path d="{right_blob}" fill="{t['heroShapeC']}">
        <animateTransform attributeName="transform" type="rotate" from="0 788 66" to="360 788 66" dur="42s" repeatCount="indefinite"/>
      </path>
    </g>
    <g opacity="0.78">
      <path d="{right_clover}" fill="{t['heroShapeB']}">
        <animateTransform attributeName="transform" type="rotate" from="360 732 214" to="0 732 214" dur="28s" repeatCount="indefinite"/>
      </path>
    </g>
    <g opacity="0.65">
      <path d="{right_gear}" fill="{t['heroShapeA']}">
        <animateTransform attributeName="transform" type="rotate" from="0 816 174" to="360 816 174" dur="18s" repeatCount="indefinite"/>
      </path>
    </g>
    <path d="{spark}" fill="{t['primary']}">
      <animate attributeName="opacity" values="0.45;1;0.45" dur="3.4s" repeatCount="indefinite"/>
    </path>
  </g>

  <!-- Rotating Scalloped M3 Avatar Frame + Stationary Avatar -->
  <g>
    <path d="{outer_scallop}" fill="{t['primary']}">
      <animateTransform attributeName="transform" type="rotate" from="0 {ax} {ay}" to="360 {ax} {ay}" dur="26s" repeatCount="indefinite"/>
    </path>
  </g>
  <g clip-path="url(#avatar-scallop-clip)">
    {avatar_inner}
  </g>

  <!-- Headline & Animated Subtitle -->
  <text x="248" y="68" font-family="{FONT_SANS}" font-size="18" font-weight="500" fill="{t['onSurfaceVariant']}">Hi, I'm</text>
  <text x="248" y="122" font-family="{FONT_SANS}" font-size="52" font-weight="800" letter-spacing="-1.5" fill="{t['onSurface']}">{esc(name)}</text>

  <!-- Crossfading Role Lines + Blinking Cursor -->
  <text class="role-a" x="248" y="158" font-family="{FONT_SANS}" font-size="17.5" font-weight="500" fill="{t['onSurfaceVariant']}">{esc(role)}</text>
  <text class="role-b" x="248" y="158" font-family="{FONT_SANS}" font-size="17.5" font-weight="500" fill="{t['primary']}" opacity="0">{esc(alt_role)}</text>
  <rect class="caret" x="{caret_x:.1f}" y="142" width="2.8" height="20" rx="1.4" fill="{t['primary']}"/>

  <!-- 3 M3 Tonal Chips -->
  {''.join(chips_svg)}
"""
    return svg_wrap(w, h, body)


def build_about_svg(cfg: dict[str, Any], theme_name: str) -> str:
    """Material 3 Expressive List Card (borderless Surface Container + tonal rows)."""
    t = THEMES[theme_name]
    w = 860
    about = cfg.get("about", {})
    title = about.get("title", "About me")
    rows: list[dict[str, Any]] = about.get("rows", [])
    h = 92 + len(rows) * 52

    badge_scallop = scalloped_path(46, 44, r_base=17, amp=2.4, lobes=8)

    rows_svg = []
    ry = 80
    for idx, row in enumerate(rows):
        bg, fg = tone_colors(t, row.get("tone", "primary"))
        icon_name = row.get("icon", "sparkles")
        txt = row.get("text", "")
        rows_svg.append(
            f'<rect x="26" y="{ry}" width="{w - 52}" height="42" rx="21" fill="{t["surfaceContainerHigh"]}"/>'
            f'<circle cx="48" cy="{ry + 21}" r="14" fill="{bg}"/>'
            f'{render_icon(icon_name, 40, ry + 13, 16, fg)}'
            f'<text x="74" y="{ry + 26}" font-family="{FONT_SANS}" font-size="14.5" font-weight="500" fill="{t["onSurface"]}">{esc(txt)}</text>'
        )
        ry += 52

    body = f"""
  <rect x="0" y="0" width="{w}" height="{h}" rx="34" fill="{t['surfaceContainer']}"/>

  <!-- Animated Scallop Header Badge -->
  <g>
    <path d="{badge_scallop}" fill="{t['primaryContainer']}">
      <animateTransform attributeName="transform" type="rotate" from="0 46 44" to="360 46 44" dur="22s" repeatCount="indefinite"/>
    </path>
  </g>
  {render_icon("sparkles", 37, 35, 18, t["onPrimaryContainer"])}
  <text x="76" y="51" font-family="{FONT_SANS}" font-size="21" font-weight="700" fill="{t['onSurface']}">{esc(title)}</text>

  {''.join(rows_svg)}
"""
    return svg_wrap(w, h, body)


def build_project_svg(project: dict[str, Any], theme_name: str) -> str:
    """Material 3 Expressive Filled Card with animated nested tonal header."""
    t = THEMES[theme_name]
    w, h = 422, 244
    name = project.get("name", "Project")
    tag = project.get("tag", "Project")
    desc = project.get("description", ["", ""])
    lang = project.get("language", "TypeScript")
    lang_color = project.get("lang_color", t["primary"])
    badge = project.get("badge", "Open Source")
    motif = project.get("motif", "octo")
    tone = project.get("tone", "primary")

    header_bg, header_fg = tone_colors(t, tone)
    accent = t["primary"] if tone == "primary" else t["secondary"]

    if motif == "octo":
        art = (
            f'<circle cx="326" cy="56" r="54" fill="{accent}" opacity="0.16">'
            f'<animate attributeName="r" values="50;58;50" dur="5s" repeatCount="indefinite"/>'
            f'</circle>'
            f'<g>'
            f'<path d="{scalloped_path(68, 54, r_base=30, amp=4.2, lobes=10)}" fill="{accent}">'
            f'<animateTransform attributeName="transform" type="rotate" from="0 68 54" to="360 68 54" dur="20s" repeatCount="indefinite"/>'
            f'</path>'
            f'</g>'
            f'<polygon points="62,43 62,65 80,54" fill="{header_bg}"/>'
            f'<rect x="114" y="34" width="96" height="14" rx="7" fill="{header_fg}" opacity="0.24"/>'
            f'<rect x="114" y="56" width="66" height="14" rx="7" fill="{header_fg}" opacity="0.15"/>'
        )
    else:
        art = (
            f'<rect x="274" y="18" width="112" height="72" rx="36" fill="{accent}" opacity="0.16"/>'
            f'<g>'
            f'<path d="{scalloped_path(68, 54, r_base=30, amp=5.2, lobes=4)}" fill="{accent}">'
            f'<animateTransform attributeName="transform" type="rotate" from="360 68 54" to="0 68 54" dur="24s" repeatCount="indefinite"/>'
            f'</path>'
            f'</g>'
            f'<g>'
            f'<path d="M68 42v18m0 0l-7-7m7 7l7-7" stroke="{header_bg}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
            f'<animateTransform attributeName="transform" type="translate" values="0 -2; 0 3; 0 -2" dur="2.2s" repeatCount="indefinite"/>'
            f'</path>'
            f'</g>'
            f'<rect x="114" y="34" width="108" height="14" rx="7" fill="{header_fg}" opacity="0.24"/>'
            f'<rect x="114" y="56" width="76" height="14" rx="7" fill="{header_fg}" opacity="0.15"/>'
        )

    tag_w = estimate_text_width(tag, 12.0, bold=True) + 22.0
    badge_w = estimate_text_width(badge, 12.0, bold=True) + 24.0

    body = f"""
  <defs>
    <clipPath id="art-clip">
      <rect x="12" y="12" width="{w - 24}" height="84" rx="22"/>
    </clipPath>
  </defs>

  <rect x="0" y="0" width="{w}" height="{h}" rx="32" fill="{t['surfaceContainer']}"/>

  <g clip-path="url(#art-clip)">
    <rect x="12" y="12" width="{w - 24}" height="84" rx="22" fill="{header_bg}"/>
    {art}
  </g>

  <circle cx="378" cy="54" r="18" fill="{t['surfaceContainerLowest']}" opacity="0.92"/>
  <path d="M373 59l10-10M375 49h8v8" fill="none" stroke="{t['onSurface']}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>

  <text x="24" y="132" font-family="{FONT_SANS}" font-size="21" font-weight="700" letter-spacing="-0.3" fill="{t['onSurface']}">{esc(name)}</text>
  <rect x="{w - 24 - tag_w:.1f}" y="112" width="{tag_w:.1f}" height="26" rx="13" fill="{t['surfaceContainerHigh']}"/>
  <text x="{w - 24 - tag_w / 2:.1f}" y="129" text-anchor="middle" font-family="{FONT_SANS}" font-size="12" font-weight="600" fill="{t['onSurfaceVariant']}">{esc(tag)}</text>

  <text x="24" y="162" font-family="{FONT_SANS}" font-size="14" fill="{t['onSurfaceVariant']}">{esc(desc[0] if len(desc) > 0 else "")}</text>
  <text x="24" y="182" font-family="{FONT_SANS}" font-size="14" fill="{t['onSurfaceVariant']}">{esc(desc[1] if len(desc) > 1 else "")}</text>

  <circle cx="31" cy="215" r="5.5" fill="{esc(lang_color)}"/>
  <text x="44" y="219.5" font-family="{FONT_SANS}" font-size="13.5" font-weight="600" fill="{t['onSurface']}">{esc(lang)}</text>

  <rect x="{w - 24 - badge_w:.1f}" y="200" width="{badge_w:.1f}" height="28" rx="14" fill="{header_bg}"/>
  <text x="{w - 24 - badge_w / 2:.1f}" y="218" text-anchor="middle" font-family="{FONT_SANS}" font-size="12" font-weight="700" fill="{header_fg}">{esc(badge)}</text>
"""
    return svg_wrap(w, h, body)


def build_stats_svg(cfg: dict[str, Any], theme_name: str) -> str:
    t = THEMES[theme_name]
    w, h = 860, 224
    gap = 16
    left_w = 406
    right_x = left_w + gap
    right_w = w - right_x

    stats = cfg.get("stats", {})
    metrics = [
        ("Commits / Year", stats.get("contributions", "203"), "primary"),
        ("Repositories", stats.get("repos", "13"), "secondary"),
        ("Public Stars", stats.get("stars", "6"), "tertiary"),
        ("Followers", stats.get("followers", "1"), "surface"),
    ]

    tiles_svg = []
    tile_w = 172
    tile_h = 56
    for idx, (label, val, tone) in enumerate(metrics):
        col = idx % 2
        row = idx // 2
        tx = 24 + col * (tile_w + 14)
        ty = 78 + row * (tile_h + 12)
        bg, fg = tone_colors(t, tone)
        tiles_svg.append(
            f'<rect x="{tx}" y="{ty}" width="{tile_w}" height="{tile_h}" rx="20" fill="{bg}"/>'
            f'<text x="{tx + 16}" y="{ty + 28}" font-family="{FONT_SANS}" font-size="20" font-weight="800" fill="{fg}">{esc(val)}</text>'
            f'<text x="{tx + 16}" y="{ty + 45}" font-family="{FONT_SANS}" font-size="11.5" font-weight="600" fill="{fg}" opacity="0.82">{esc(label)}</text>'
        )

    langs: list[dict[str, Any]] = stats.get("languages", [])
    total_pct = sum(float(l.get("percent", 0)) for l in langs) or 100.0
    bar_x = right_x + 26.0
    bar_y = 84.0
    bar_w = right_w - 52.0
    bar_h = 16.0
    seg_gap = 5.0
    usable_w = bar_w - seg_gap * max(0, len(langs) - 1)

    bars_svg = []
    legend_svg = []
    cur_x = bar_x
    for idx, lang in enumerate(langs[:4]):
        pct = float(lang.get("percent", 0))
        seg_w = max(18.0, usable_w * (pct / total_pct))
        c = lang.get(f"color_{theme_name}", t["primary"])
        bars_svg.append(
            f'<rect x="{cur_x:.1f}" y="{bar_y:.1f}" width="{seg_w:.1f}" height="{bar_h:.1f}" rx="8" fill="{esc(c)}"/>'
        )
        cur_x += seg_w + seg_gap

        col = idx % 2
        row = idx // 2
        lx = right_x + 26 + col * 194
        ly = 122 + row * 38
        legend_svg.append(
            f'<rect x="{lx}" y="{ly}" width="180" height="30" rx="15" fill="{t["surfaceContainerHigh"]}"/>'
            f'<circle cx="{lx + 15}" cy="{ly + 15}" r="5" fill="{esc(c)}"/>'
            f'<text x="{lx + 28}" y="{ly + 19.5}" font-family="{FONT_SANS}" font-size="13" font-weight="600" fill="{t["onSurface"]}">{esc(lang.get("name", ""))}</text>'
            f'<text x="{lx + 166}" y="{ly + 19.5}" text-anchor="end" font-family="{FONT_SANS}" font-size="12.5" font-weight="700" fill="{t["onSurfaceVariant"]}">{int(round(pct))}%</text>'
        )

    # Flowing animated wavy line (extended pattern clipped cleanly)
    wavy = wavy_line_path(right_x + 20, w + 40, 204, amp=3.4, wavelength=26.0)

    body = f"""
  <defs>
    <clipPath id="wave-clip">
      <rect x="{right_x + 26}" y="192" width="{right_w - 52}" height="24"/>
    </clipPath>
  </defs>

  <rect x="0" y="0" width="{left_w}" height="{h}" rx="34" fill="{t['surfaceContainer']}"/>
  <circle cx="42" cy="42" r="18" fill="{t['primaryContainer']}"/>
  {render_icon("activity", 32, 32, 20, t["onPrimaryContainer"])}
  <text x="70" y="48" font-family="{FONT_SANS}" font-size="19" font-weight="700" fill="{t['onSurface']}">{esc(stats.get("title", "GitHub Snapshot"))}</text>
  {''.join(tiles_svg)}

  <rect x="{right_x}" y="0" width="{right_w}" height="{h}" rx="34" fill="{t['surfaceContainer']}"/>
  <circle cx="{right_x + 44}" cy="42" r="18" fill="{t['secondaryContainer']}"/>
  {render_icon("layers", right_x + 34, 32, 20, t["onSecondaryContainer"])}
  <text x="{right_x + 72}" y="48" font-family="{FONT_SANS}" font-size="19" font-weight="700" fill="{t['onSurface']}">{esc(stats.get("languages_title", "Top Languages"))}</text>
  {''.join(bars_svg)}
  {''.join(legend_svg)}
  <g clip-path="url(#wave-clip)">
    <path d="{wavy}" stroke="{t['primary']}" stroke-width="2.8" stroke-linecap="round" opacity="0.62">
      <animateTransform attributeName="transform" type="translate" from="0 0" to="-26 0" dur="2.2s" repeatCount="indefinite"/>
    </path>
  </g>
"""
    return svg_wrap(w, h, body)


def social_pill_width(count: int) -> int:
    if count <= 0:
        return 276
    if count <= 3:
        return (860 - (count - 1) * 16) // count
    return 204


def build_social_pill_svg(social: dict[str, Any], theme_name: str, width: int = 276) -> str:
    t = THEMES[theme_name]
    w, h = width, 64
    label = social.get("label", "Link")
    handle = social.get("handle", "")
    icon_name = social.get("icon", "globe")
    tone = social.get("tone", "surface")
    bg, fg = tone_colors(t, tone)

    body = f"""
  <rect x="0" y="0" width="{w}" height="{h}" rx="32" fill="{bg}"/>
  <circle cx="32" cy="32" r="18" fill="{t['surfaceContainerLowest']}" opacity="0.90"/>
  {render_icon(icon_name, 22, 22, 20, t['primary'] if tone == 'surface' else fg)}
  <text x="62" y="29" font-family="{FONT_SANS}" font-size="15" font-weight="700" fill="{fg}">{esc(label)}</text>
  <text x="62" y="47" font-family="{FONT_SANS}" font-size="12.5" font-weight="500" fill="{fg}" opacity="0.82">{esc(handle)}</text>
  <path d="M{w - 30} 37l8-8M{w - 28} 29h6v6" fill="none" stroke="{fg}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.72"/>
"""
    return svg_wrap(w, h, body)


def build_footer_svg(theme_name: str) -> str:
    t = THEMES[theme_name]
    w, h = 860, 36
    wavy_l = wavy_line_path(24, 422, 18, amp=3.8, wavelength=28.0)
    wavy_r = wavy_line_path(464, 864, 18, amp=3.8, wavelength=28.0)
    spark = four_point_star_path(430, 18, r_outer=11, r_inner=3.8)

    body = f"""
  <defs>
    <clipPath id="wave-l"><rect x="24" y="6" width="372" height="24"/></clipPath>
    <clipPath id="wave-r"><rect x="464" y="6" width="372" height="24"/></clipPath>
  </defs>
  <g clip-path="url(#wave-l)">
    <path d="{wavy_l}" stroke="{t['primary']}" stroke-width="2.8" stroke-linecap="round" opacity="0.55">
      <animateTransform attributeName="transform" type="translate" from="0 0" to="-28 0" dur="2.6s" repeatCount="indefinite"/>
    </path>
  </g>
  <path d="{spark}" fill="{t['secondary']}">
    <animateTransform attributeName="transform" type="rotate" from="0 430 18" to="360 430 18" dur="12s" repeatCount="indefinite"/>
  </path>
  <g clip-path="url(#wave-r)">
    <path d="{wavy_r}" stroke="{t['secondary']}" stroke-width="2.8" stroke-linecap="round" opacity="0.65">
      <animateTransform attributeName="transform" type="translate" from="-28 0" to="0 0" dur="2.6s" repeatCount="indefinite"/>
    </path>
  </g>
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
    name = cfg.get("display_name", "churros")
    projects: list[dict[str, Any]] = cfg.get("projects", [])
    socials: list[dict[str, Any]] = cfg.get("socials", [])

    # Use 48% so 2 project cards ALWAYS sit side-by-side inside GitHub's Profile Overview
    proj_pct = "48%" if len(projects) >= 2 else "100%"
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
                f'<a href="{url}">'
                f'{picture_tag(f"project-{idx + 1}", pname, width=proj_pct)}'
                f'</a>'
            )
        project_rows.append('<p align="center">\n  ' + "\n  &nbsp;\n  ".join(row_items) + "\n</p>")

    soc_pct = "32%" if len(socials) == 3 else ("48%" if len(socials) == 2 else "24%")
    social_links = []
    for idx, soc in enumerate(socials):
        url = esc(soc.get("url", "#"))
        lbl = esc(soc.get("label", f"Social {idx + 1}"))
        social_links.append(
            f'<a href="{url}">'
            f'{picture_tag(f"social-{idx + 1}", lbl, width=soc_pct)}'
            f'</a>'
        )

    sections = [
        f'<p align="center">\n  {picture_tag("hero", f"{name} — Material 3 Expressive Header", width="100%")}\n</p>',
        f'<p align="center">\n  {picture_tag("about", "About me", width="100%")}\n</p>',
        "\n".join(project_rows),
        f'<p align="center">\n  {picture_tag("stats", "GitHub Snapshot & Top Languages", width="100%")}\n</p>',
        '<p align="center">\n  ' + "\n  &nbsp;\n  ".join(social_links) + "\n</p>",
        f'<p align="center">\n  {picture_tag("footer", "Divider", width="100%")}\n</p>',
    ]
    return "\n\n".join(sections) + "\n"


def fetch_github_stats(username: str) -> dict[str, Any]:
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
        ("#006B5E", "#7ADBC8"),
        ("#4F5D95", "#B8C4FF"),
        ("#7D5260", "#EFB8C8"),
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

    for old_svg in ASSETS_DIR.glob("*.svg"):
        old_svg.unlink()

    for theme_name in ("light", "dark"):
        files = {
            f"hero-{theme_name}.svg": build_hero_svg(cfg, theme_name),
            f"about-{theme_name}.svg": build_about_svg(cfg, theme_name),
            f"stats-{theme_name}.svg": build_stats_svg(cfg, theme_name),
            f"footer-{theme_name}.svg": build_footer_svg(theme_name),
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
        help="Fetch live stars, followers, and languages from GitHub API",
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
