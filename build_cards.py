from __future__ import annotations
from pathlib import Path
import hashlib, json, re, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "github_config.json"
SOURCE_M3U = ROOT / "eventos_acestream.m3u"
CARDS_DIR = ROOT / "cards"

W, H = 700, 1050

SPORT_STYLES = {
    "futbol": {
        "bg1": (9, 28, 58), "bg2": (5, 86, 122), "accent": (66, 235, 172), "label": "FÚTBOL"
    },
    "baloncesto": {
        "bg1": (34, 15, 63), "bg2": (92, 44, 138), "accent": (255, 153, 68), "label": "BALONCESTO"
    },
    "tenis": {
        "bg1": (7, 41, 35), "bg2": (14, 109, 80), "accent": (193, 255, 95), "label": "TENIS"
    },
    "motor": {
        "bg1": (43, 11, 16), "bg2": (150, 26, 44), "accent": (255, 89, 89), "label": "MOTOR"
    },
    "ciclismo": {
        "bg1": (41, 31, 8), "bg2": (130, 92, 11), "accent": (255, 214, 64), "label": "CICLISMO"
    },
    "combate": {
        "bg1": (34, 11, 31), "bg2": (118, 21, 92), "accent": (255, 113, 196), "label": "COMBATE"
    },
    "default": {
        "bg1": (8, 18, 47), "bg2": (30, 44, 93), "accent": (230, 236, 255), "label": "DEPORTE"
    },
}

def load_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

def infer_sport(group_title: str, tvg_name: str, title: str) -> str:
    blob = f"{group_title} {tvg_name} {title}".lower()
    checks = [
        ("futbol", ["liga", "champions", "europa", "premier", "fútbol", "futbol", "copa", "1rfef", "laliga", "serie a", "bundesliga"]),
        ("baloncesto", ["nba", "euroleague", "euroliga", "baloncesto", "basket"]),
        ("tenis", ["atp", "wta", "tenis", "roland", "wimbledon", "masters", "montecarlo"]),
        ("motor", ["formula", "f1", "motogp", "motor", "nascar", "rally"]),
        ("ciclismo", ["ciclismo", "tour", "giro", "vuelta"]),
        ("combate", ["ufc", "boxeo", "mma", "combate"]),
    ]
    for sport, words in checks:
        if any(w in blob for w in words):
            return sport
    return "default"

def normalize_channel(name: str) -> str:
    s = re.sub(r"^[▶>\-\s]+", "", name).strip()
    s = re.sub(r"\s+\*+$", "", s).strip()
    s = re.sub(r"\s{2,}", " ", s)
    s = s.replace("M+ ", "Movistar ")
    return s

def split_title(title: str):
    parts = [p.strip() for p in title.split("|")]
    return (parts[0] if len(parts) > 0 else "",
            parts[1] if len(parts) > 1 else title.strip(),
            parts[2] if len(parts) > 2 else "")

def hash_id(*parts: str) -> str:
    return hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()[:16]

def get_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates += [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    candidates += [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()

def rounded_gradient_background(size, c1, c2):
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 255))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        for x in range(w):
            px[x, y] = (r, g, b, 255)
    return img

def draw_centered(draw, box, text, font, fill, line_spacing=10, width_chars=18):
    x1, y1, x2, y2 = box
    lines = textwrap.wrap(text, width=width_chars) or [text]
    sizes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    heights = [(b[3] - b[1]) for b in sizes]
    total_h = sum(heights) + line_spacing * max(0, len(lines) - 1)
    y = y1 + (y2 - y1 - total_h) // 2
    for line, bbox in zip(lines, sizes):
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = x1 + (x2 - x1 - tw) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += th + line_spacing

def ellipsize(draw, text, font, max_width):
    if draw.textbbox((0,0), text, font=font)[2] <= max_width:
        return text
    base = text
    while len(base) > 3:
        base = base[:-1]
        candidate = base.rstrip() + "…"
        if draw.textbbox((0,0), candidate, font=font)[2] <= max_width:
            return candidate
    return text

def make_card(out_path: Path, group_title: str, tvg_name: str, title: str):
    sport = infer_sport(group_title, tvg_name, title)
    style = SPORT_STYLES[sport]
    time_txt, match_txt, channel_txt = split_title(title)
    channel_txt = normalize_channel(channel_txt or tvg_name or "CANAL")
    match_txt = re.sub(r"\s+", " ", match_txt).strip()

    img = rounded_gradient_background((W, H), style["bg1"], style["bg2"])
    draw = ImageDraw.Draw(img)

    # glossy overlays
    glow = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-100, -120, 540, 320), fill=(255,255,255,45))
    gd.ellipse((250, 650, 900, 1300), fill=(255,255,255,18))
    gd.rectangle((0, H-240, W, H), fill=(2,5,14,110))
    glow = glow.filter(ImageFilter.GaussianBlur(34))
    img.alpha_composite(glow)

    # outer frame
    draw.rounded_rectangle((10, 10, W-10, H-10), radius=38, outline=(255,255,255,55), width=2)

    # accent line
    draw.rounded_rectangle((56, 1000, W-56, 1014), radius=7, fill=tuple(style["accent"]))

    font_label = get_font(30, bold=True)
    font_time = get_font(34, bold=True)
    font_title = get_font(60, bold=True)
    font_group = get_font(30, bold=False)
    font_channel = get_font(28, bold=True)

    # sport pill - white with black text
    sport_label = style["label"]
    pill_bbox = draw.textbbox((0,0), sport_label, font=font_label)
    pill_w = (pill_bbox[2] - pill_bbox[0]) + 48
    draw.rounded_rectangle((34, 30, 34 + pill_w, 86), radius=24, fill=(255,255,255,225))
    draw.text((58, 42), sport_label, font=font_label, fill=(0,0,0,255))
    img.convert("RGB").save(out_path, format="PNG", optimize=True)
    # time pill
    if time_txt:
        time_bbox = draw.textbbox((0,0), time_txt, font=font_time)
        tw = (time_bbox[2] - time_bbox[0]) + 48
        draw.rounded_rectangle((W - tw - 34, 30, W - 34, 86), radius=24, fill=(255,255,255,225))
        draw.text((W - tw - 10, 42), time_txt, font=font_time, fill=(0,0,0,255))

    # central event title
    draw_centered(
        draw,
        (68, 220, W-68, 560),
        match_txt,
        font_title,
        (248,250,255,255),
        line_spacing=8,
        width_chars=19
    )

    # subtle group title
    gt = re.sub(r"\s+", " ", group_title).strip()
    if gt:
        gt_clean = gt.replace("TV · ", "").replace("TV . ", "").strip()
        draw_centered(
            draw,
            (80, 620, W-80, 700),
            gt_clean,
            font_group,
            (215,224,245,220),
            line_spacing=6,
            width_chars=28
        )

    # channel pill dark
    channel_txt = ellipsize(draw, channel_txt, font_channel, 320)
    ch_bbox = draw.textbbox((0,0), channel_txt, font=font_channel)
    ch_w = (ch_bbox[2] - ch_bbox[0]) + 54
    left = (W - ch_w) // 2
    draw.rounded_rectangle((left, 805, left + ch_w, 860), radius=26, fill=(0,0,0,160))
    draw.text((left + 27, 820), channel_txt, font=font_channel, fill=(255,255,255,255))

def parse_attrs(extinf_line: str):
    attrs = {}
    for k, v in re.findall(r'([a-zA-Z0-9\-_]+)="([^"]*)"', extinf_line):
        attrs[k] = v
    return attrs

def rebuild_extinf(attrs: dict, display_name: str) -> str:
    ordered = ["tvg-id", "tvg-name", "tvg-logo", "group-title"]
    parts = []
    for k in ordered:
        if attrs.get(k):
            parts.append(f'{k}="{attrs[k]}"')
    for k, v in attrs.items():
        if k not in ordered and v:
            parts.append(f'{k}="{v}"')
    return f'#EXTINF:-1 {" ".join(parts)},{display_name}'

def build():
    cfg = load_config()
    base_url = cfg["base_url"].rstrip("/")
    playlist_name = cfg.get("playlist_name", "eventos_acestream_hosting_pro.m3u")

    raw = SOURCE_M3U.read_text(encoding="utf-8", errors="ignore").splitlines()
    out_lines = ["#EXTM3U"]
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    i = 0
    while i < len(raw):
        line = raw[i].rstrip("\n")
        if line.startswith("#EXTINF"):
            attrs = parse_attrs(line)
            display_name = line.split(",", 1)[1] if "," in line else ""
            group_title = attrs.get("group-title", "")
            tvg_name = attrs.get("tvg-name", "")
            uid = hash_id(group_title, tvg_name, display_name)
            filename = f"{uid}.png"
            make_card(CARDS_DIR / filename, group_title, tvg_name, display_name)
            attrs["tvg-id"] = attrs.get("tvg-id", normalize_channel(tvg_name).replace(" ", "."))
            attrs["tvg-logo"] = f"{base_url}/cards/{filename}"
            out_lines.append(rebuild_extinf(attrs, display_name))
            if i + 1 < len(raw):
                out_lines.append(raw[i + 1].rstrip("\n"))
                i += 2
                continue
        elif line and line != "#EXTM3U":
            out_lines.append(line)
        i += 1

    output = ROOT / playlist_name
    output.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"OK: {output}")

if __name__ == "__main__":
    build()
