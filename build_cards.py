from __future__ import annotations
from pathlib import Path
import hashlib
import json
import re
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "github_config.json"
SOURCE_M3U = ROOT / "eventos_acestream.m3u"
CARDS_DIR = ROOT / "cards"

W, H = 700, 1050

SPORT_STYLES = {
    "futbol": {
        "bg1": (8, 16, 30),
        "bg2": (6, 54, 86),
        "accent": (73, 235, 171),
        "label": "FÚTBOL",
    },
    "baloncesto": {
        "bg1": (20, 15, 34),
        "bg2": (74, 42, 116),
        "accent": (255, 145, 62),
        "label": "BALONCESTO",
    },
    "tenis": {
        "bg1": (14, 35, 31),
        "bg2": (8, 83, 64),
        "accent": (196, 255, 104),
        "label": "TENIS",
    },
    "motor": {
        "bg1": (28, 12, 16),
        "bg2": (112, 24, 36),
        "accent": (255, 95, 95),
        "label": "MOTOR",
    },
    "ciclismo": {
        "bg1": (34, 27, 9),
        "bg2": (118, 89, 12),
        "accent": (255, 214, 74),
        "label": "CICLISMO",
    },
    "combate": {
        "bg1": (28, 10, 22),
        "bg2": (105, 19, 78),
        "accent": (255, 113, 196),
        "label": "COMBATE",
    },
    "default": {
        "bg1": (12, 19, 40),
        "bg2": (27, 40, 84),
        "accent": (230, 236, 255),
        "label": "DEPORTE",
    },
}


def load_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def infer_sport(group_title: str, tvg_name: str, title: str) -> str:
    blob = f"{group_title} {tvg_name} {title}".lower()

    if any(x in blob for x in [
        "nba", "euroliga", "euroleague", "baloncesto", "basket", "acb", "básquet"
    ]):
        return "baloncesto"

    if any(x in blob for x in [
        "atp", "wta", "tenis", "wimbledon", "roland", "montecarlo", "masters", "us open"
    ]):
        return "tenis"

    if any(x in blob for x in [
        "formula 1", "formula1", "f1", "motogp", "moto gp", "nascar", "rally", "motor"
    ]):
        return "motor"

    if any(x in blob for x in [
        "tour", "giro", "vuelta", "ciclismo", "uci"
    ]):
        return "ciclismo"

    if any(x in blob for x in [
        "ufc", "boxeo", "mma", "combate", "wrestling"
    ]):
        return "combate"

    if any(x in blob for x in [
        "champions", "laliga", "liga", "premier", "bundesliga", "serie a",
        "futbol", "fútbol", "copa", "1rfef", "supercopa", "coppa",
        "europa league", "conference league", "ligue 1", "eredivisie"
    ]):
        return "futbol"

    return "default"


def normalize_channel(name: str) -> str:
    s = re.sub(r"^[▶>\-\s]+", "", name or "").strip()
    s = re.sub(r"\s+\*+$", "", s).strip()
    s = re.sub(r"\s{2,}", " ", s)

    replacements = {
        "M+ ": "Movistar ",
        "M+DEPORTES": "MOVISTAR DEPORTES",
        "M+ DEPORTES": "MOVISTAR DEPORTES",
        "M+ LALIGA": "MOVISTAR LALIGA",
        "M+ LIGA": "MOVISTAR LIGA",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)

    return s.strip()


def split_title(title: str):
    parts = [p.strip() for p in (title or "").split("|")]
    time_txt = parts[0] if len(parts) > 0 else ""
    match_txt = parts[1] if len(parts) > 1 else (title or "").strip()
    channel_txt = parts[2] if len(parts) > 2 else ""
    return time_txt, match_txt, channel_txt


def clean_match_text(text: str) -> str:
    s = re.sub(r"\s+", " ", text or "").strip()
    s = s.replace(" vs. ", " vs ")
    s = s.replace(" Vs ", " vs ")
    s = s.replace(" v ", " vs ")
    return s


def clean_group_text(text: str) -> str:
    s = re.sub(r"\s+", " ", text or "").strip()
    s = s.replace("TV · ", "").replace("TV . ", "").replace("TV·", "")
    s = s.replace("Regular - TV channel", "Regular")
    s = s.replace(" - TV channel", "")
    return s.strip()


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


def wrap_text_by_pixels(draw, text, font, max_width):
    words = (text or "").split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        test = current + " " + word
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_centered_lines(draw, box, lines, font, fill, line_spacing=8):
    x1, y1, x2, y2 = box
    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    heights = [(b[3] - b[1]) for b in boxes]
    total_h = sum(heights) + line_spacing * max(0, len(lines) - 1)
    y = y1 + (y2 - y1 - total_h) // 2
    for line, bbox in zip(lines, boxes):
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = x1 + (x2 - x1 - tw) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += th + line_spacing


def fit_title_lines(draw, text, font, max_width, max_lines=3):
    lines = wrap_text_by_pixels(draw, text, font, max_width)
    if len(lines) <= max_lines:
        return lines

    compact = textwrap.wrap(text, width=16)
    if len(compact) <= max_lines:
        return compact

    result = compact[:max_lines]
    last = result[-1]
    while draw.textbbox((0, 0), last + "…", font=font)[2] > max_width and len(last) > 3:
        last = last[:-1]
    result[-1] = last.rstrip() + "…"
    return result


def ellipsize(draw, text, font, max_width):
    text = text or ""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    base = text
    while len(base) > 3:
        base = base[:-1]
        candidate = base.rstrip() + "…"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            return candidate
    return text


def make_card(out_path: Path, group_title: str, tvg_name: str, title: str):
    sport = infer_sport(group_title, tvg_name, title)
    style = SPORT_STYLES[sport]

    time_txt, match_txt, channel_txt = split_title(title)
    match_txt = clean_match_text(match_txt)
    group_txt = clean_group_text(group_title)
    channel_txt = normalize_channel(channel_txt or tvg_name or "CANAL")

    img = Image.new("RGBA", (W, H), style["bg1"] + (255,))
    draw = ImageDraw.Draw(img)

    overlay = rounded_gradient_background((W, H), style["bg1"], style["bg2"])
    overlay.putalpha(185)
    img.alpha_composite(overlay)

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-100, -120, 450, 240), fill=(255, 255, 255, 18))
    gd.ellipse((220, 760, 900, 1250), fill=(255, 255, 255, 10))
    gd.rectangle((0, H - 250, W, H), fill=(0, 0, 0, 78))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    img.alpha_composite(glow)

    draw.rounded_rectangle((10, 10, W - 10, H - 10), radius=36, outline=(255, 255, 255, 55), width=2)
    draw.rounded_rectangle((56, 995, W - 56, 1008), radius=6, fill=tuple(style["accent"]))

    font_label = get_font(28, bold=True)
    font_time = get_font(34, bold=True)
    font_title = get_font(64, bold=True)
    font_group = get_font(29, bold=False)
    font_channel = get_font(24, bold=True)

    sport_label = style["label"]
    sport_box = draw.textbbox((0, 0), sport_label, font=font_label)
    pill_w = (sport_box[2] - sport_box[0]) + 44
    draw.rounded_rectangle((34, 30, 34 + pill_w, 84), radius=22, fill=(255, 255, 255, 236))
    draw.text((56, 41), sport_label, font=font_label, fill=(0, 0, 0, 255))

    if time_txt:
        time_box = draw.textbbox((0, 0), time_txt, font=font_time)
        tw = (time_box[2] - time_box[0]) + 42
        draw.rounded_rectangle((W - tw - 34, 30, W - 34, 84), radius=22, fill=(255, 255, 255, 236))
        draw.text((W - tw - 14, 39), time_txt, font=font_time, fill=(0, 0, 0, 255))

    title_lines = fit_title_lines(draw, match_txt, font_title, max_width=W - 150, max_lines=3)
    draw_centered_lines(
        draw,
        (72, 255, W - 72, 585),
        title_lines,
        font_title,
        (248, 250, 255, 255),
        line_spacing=4
    )

    if group_txt:
        group_txt = ellipsize(draw, group_txt, font_group, W - 180)
        draw_centered_lines(
            draw,
            (90, 650, W - 90, 735),
            [group_txt],
            font_group,
            (214, 224, 245, 228),
            line_spacing=4
        )

    channel_txt = ellipsize(draw, channel_txt, font_channel, 350)
    ch_box = draw.textbbox((0, 0), channel_txt, font=font_channel)
    ch_w = (ch_box[2] - ch_box[0]) + 46
    left = (W - ch_w) // 2
    draw.rounded_rectangle((left, 812, left + ch_w, 860), radius=24, fill=(0, 0, 0, 170))
    draw.text((left + 23, 825), channel_txt, font=font_channel, fill=(255, 255, 255, 255))

    img.convert("RGB").save(out_path, format="PNG", optimize=True)


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
