from __future__ import annotations
from pathlib import Path
import hashlib, json, re, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "github_config.json"
SOURCE_M3U = ROOT / "eventos_acestream.m3u"
CARDS_DIR = ROOT / "cards"
BACKDROPS_DIR = ROOT / "backdrops"
CHANNEL_LOGOS_DIR = ROOT / "channel_logos"

CARD_W, CARD_H = 700, 1050
BG_W, BG_H = 1280, 720

SPORT_STYLES = {
    "futbol": {"bg1": (6,12,24), "bg2": (4,64,104), "accent": (74,235,174), "label": "FÚTBOL"},
    "baloncesto": {"bg1": (18,12,30), "bg2": (86,46,126), "accent": (255,151,73), "label": "BALONCESTO"},
    "tenis": {"bg1": (10,34,28), "bg2": (10,96,73), "accent": (193,255,103), "label": "TENIS"},
    "motor": {"bg1": (26,10,14), "bg2": (126,24,36), "accent": (255,96,96), "label": "MOTOR"},
    "ciclismo": {"bg1": (35,26,8), "bg2": (128,93,12), "accent": (255,214,74), "label": "CICLISMO"},
    "combate": {"bg1": (28,10,22), "bg2": (110,20,86), "accent": (255,113,196), "label": "COMBATE"},
    "default": {"bg1": (10,18,36), "bg2": (30,44,90), "accent": (230,236,255), "label": "DEPORTE"},
}
CHANNEL_BADGES = [
    {"match": ["dazn"], "text": "DAZN", "bg": (15,15,18), "fg": (255,255,255), "file": "dazn.png"},
    {"match": ["movistar laliga", "m+ laliga"], "text": "M+ LALIGA", "bg": (20,44,96), "fg": (255,255,255), "file": "movistar_laliga.png"},
    {"match": ["movistar liga", "m+ liga"], "text": "M+ LIGA", "bg": (24,58,118), "fg": (255,255,255), "file": "movistar_liga.png"},
    {"match": ["movistar deportes", "m+ deportes"], "text": "M DEPORTES", "bg": (31,48,88), "fg": (255,255,255), "file": "movistar_deportes.png"},
    {"match": ["liga de campeones", "champions"], "text": "M CHAMP", "bg": (17,33,78), "fg": (255,255,255), "file": "m_champ.png"},
    {"match": ["eurosport"], "text": "EUROSPORT", "bg": (22,39,92), "fg": (255,255,255), "file": "eurosport.png"},
    {"match": ["nba tv"], "text": "NBA TV", "bg": (184,28,28), "fg": (255,255,255), "file": "nba_tv.png"},
    {"match": ["teledeporte"], "text": "TDP", "bg": (37,111,176), "fg": (255,255,255), "file": "teledeporte.png"},
    {"match": ["vamos"], "text": "VAMOS", "bg": (31,87,180), "fg": (255,255,255), "file": "vamos.png"},
]

def load_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
def infer_sport(group_title, tvg_name, title):
    blob = f"{group_title} {tvg_name} {title}".lower()
    if any(x in blob for x in ["nba","euroliga","euroleague","baloncesto","basket","acb","básquet"]): return "baloncesto"
    if any(x in blob for x in ["tenis","atp","wta","wimbledon","roland","montecarlo","masters","us open"]): return "tenis"
    if any(x in blob for x in ["f1","formula","motogp","moto gp","motor","rally","nascar"]): return "motor"
    if any(x in blob for x in ["tour","giro","vuelta","ciclismo","uci"]): return "ciclismo"
    if any(x in blob for x in ["ufc","mma","boxeo","combate","wrestling"]): return "combate"
    if any(x in blob for x in ["liga","champions","premier","futbol","fútbol","laliga","bundesliga","serie a","1rfef","copa"]): return "futbol"
    return "default"
def normalize_channel(name):
    s = re.sub(r"^[▶>\-\s]+", "", name or "").strip()
    s = re.sub(r"\s+\*+$", "", s).strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s.replace("M+ ", "Movistar ").strip()
def split_title(title):
    parts = [p.strip() for p in (title or "").split("|")]
    return (parts[0] if len(parts)>0 else "", parts[1] if len(parts)>1 else (title or "").strip(), parts[2] if len(parts)>2 else "")
def clean_match_text(text):
    return re.sub(r"\s+", " ", (text or "").replace(" vs. ", " vs ").replace(" Vs ", " vs ").replace(" v ", " vs ")).strip()
def clean_group_text(text):
    s = re.sub(r"\s+", " ", text or "").strip()
    return s.replace("TV · ", "").replace("TV . ", "").replace("TV·", "").replace("Regular - TV channel", "Regular").replace(" - TV channel", "").strip()
def hash_id(*parts): return hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()[:16]
def get_font(size, bold=False):
    c = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in c:
        if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default()
def rounded_gradient_background(size, c1, c2):
    w,h = size
    img = Image.new("RGBA", size, (0,0,0,255))
    px = img.load()
    for y in range(h):
        t = y/max(1,h-1)
        r = int(c1[0]*(1-t)+c2[0]*t); g = int(c1[1]*(1-t)+c2[1]*t); b = int(c1[2]*(1-t)+c2[2]*t)
        for x in range(w): px[x,y]=(r,g,b,255)
    return img
def draw_centered_lines(draw, box, lines, font, fill, line_spacing=8):
    x1,y1,x2,y2 = box
    boxes = [draw.textbbox((0,0), line, font=font) for line in lines]
    heights = [b[3]-b[1] for b in boxes]
    total_h = sum(heights)+line_spacing*max(0,len(lines)-1)
    y = y1+(y2-y1-total_h)//2
    for line,bbox in zip(lines,boxes):
        tw = bbox[2]-bbox[0]; th = bbox[3]-bbox[1]
        x = x1+(x2-x1-tw)//2
        draw.text((x,y), line, font=font, fill=fill)
        y += th+line_spacing
def fit_title_lines(draw, text, font, max_width, max_lines=3):
    words = (text or "").split()
    if not words: return [""]
    lines=[]; current=words[0]
    for word in words[1:]:
        test=current+" "+word
        if draw.textbbox((0,0), test, font=font)[2] <= max_width: current=test
        else: lines.append(current); current=word
    lines.append(current)
    if len(lines)<=max_lines: return lines
    compact=textwrap.wrap(text,width=16)
    if len(compact)<=max_lines: return compact
    result=compact[:max_lines]; last=result[-1]
    while draw.textbbox((0,0), last+"…", font=font)[2] > max_width and len(last)>3: last=last[:-1]
    result[-1]=last.rstrip()+"…"; return result
def ellipsize(draw, text, font, max_width):
    text = text or ""
    if draw.textbbox((0,0), text, font=font)[2] <= max_width: return text
    base=text
    while len(base)>3:
        base=base[:-1]; cand=base.rstrip()+"…"
        if draw.textbbox((0,0), cand, font=font)[2] <= max_width: return cand
    return text
def get_channel_badge(channel_txt):
    blob=(channel_txt or "").lower()
    for item in CHANNEL_BADGES:
        if any(k in blob for k in item["match"]): return item
    cleaned=re.sub(r"[^A-Za-z0-9+ ]","",channel_txt or "").upper().split()
    text = "TV" if not cleaned else (cleaned[0][:10] if len(cleaned)==1 else " ".join(cleaned[:2])[:12])
    return {"text": text, "bg": (255,255,255), "fg": (0,0,0), "file": None}
def draw_badge(draw, x, y, text, bg, fg, font, accent=None):
    bbox=draw.textbbox((0,0), text, font=font)
    w=max(110,min(240,(bbox[2]-bbox[0])+34)); h=52
    draw.rounded_rectangle((x,y,x+w,y+h), radius=16, fill=bg)
    tw=bbox[2]-bbox[0]; th=bbox[3]-bbox[1]
    draw.text((x+(w-tw)//2, y+(h-th)//2-1), text, font=font, fill=fg)
    if accent: draw.rounded_rectangle((x+10,y+h-7,x+w-10,y+h-3), radius=2, fill=accent)
def paste_channel_logo(base_img, logo_path, x, y, box_w, box_h):
    logo = Image.open(logo_path).convert("RGBA"); logo.thumbnail((box_w,box_h), Image.LANCZOS)
    pad=10; card=Image.new("RGBA",(box_w+pad*2,box_h+pad*2),(0,0,0,0))
    d=ImageDraw.Draw(card); d.rounded_rectangle((0,0,card.size[0],card.size[1]), radius=18, fill=(255,255,255,235))
    lx=(card.size[0]-logo.size[0])//2; ly=(card.size[1]-logo.size[1])//2
    card.alpha_composite(logo,(lx,ly)); base_img.alpha_composite(card,(x,y))
def make_card_and_backdrop(uid, group_title, tvg_name, title):
    sport=infer_sport(group_title,tvg_name,title); style=SPORT_STYLES[sport]
    time_txt, match_txt, channel_txt = split_title(title)
    match_txt=clean_match_text(match_txt); group_txt=clean_group_text(group_title); channel_txt=normalize_channel(channel_txt or tvg_name or "CANAL")
    badge=get_channel_badge(channel_txt)

    img=Image.new("RGBA",(CARD_W,CARD_H),style["bg1"]+(255,))
    overlay=rounded_gradient_background((CARD_W,CARD_H),style["bg1"],style["bg2"]); overlay.putalpha(210); img.alpha_composite(overlay)
    glow=Image.new("RGBA",(CARD_W,CARD_H),(0,0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse((-120,-160,520,260), fill=(255,255,255,22)); gd.rectangle((0,0,CARD_W,CARD_H), fill=(0,0,0,48)); gd.rectangle((0,CARD_H-280,CARD_W,CARD_H), fill=(0,0,0,76))
    glow=glow.filter(ImageFilter.GaussianBlur(28)); img.alpha_composite(glow)
    frame=Image.new("RGBA",(CARD_W,CARD_H),(0,0,0,0)); fd=ImageDraw.Draw(frame); fd.rounded_rectangle((10,10,CARD_W-10,CARD_H-10), radius=36, outline=(255,255,255,40), width=2); img.alpha_composite(frame)
    draw=ImageDraw.Draw(img)
    font_label=get_font(26,True); font_time=get_font(30,True); font_title=get_font(60,True); font_group=get_font(28,False); font_channel=get_font(24,True); font_badge=get_font(22,True)
    draw.rounded_rectangle((56,994,CARD_W-56,1008), radius=6, fill=tuple(style["accent"]))
    draw_badge(draw,34,30,style["label"],(255,255,255),(0,0,0),font_label)
    if time_txt:
        time_bbox=draw.textbbox((0,0),time_txt,font=font_time); tw=max(110,(time_bbox[2]-time_bbox[0])+34)
        draw_badge(draw,CARD_W-tw-34,30,time_txt,(255,255,255),(0,0,0),font_time)
    logo_done=False
    if badge.get("file"):
        lp=CHANNEL_LOGOS_DIR / badge["file"]
        if lp.exists(): paste_channel_logo(img, lp, CARD_W-190,118,120,56); logo_done=True
    draw=ImageDraw.Draw(img)
    if not logo_done:
        badge_text=badge["text"]; badge_w=max(120,min(220,draw.textbbox((0,0),badge_text,font=font_badge)[2]+36))
        draw_badge(draw,CARD_W-badge_w-50,125,badge_text,tuple(badge["bg"]),tuple(badge["fg"]),font_badge,tuple(style["accent"]))
    title_lines=fit_title_lines(draw,match_txt,font_title,max_width=CARD_W-150,max_lines=3)
    draw_centered_lines(draw,(70,255,CARD_W-70,590),title_lines,font_title,(255,255,255,255),line_spacing=4)
    if group_txt:
        group_txt=ellipsize(draw,group_txt,font_group,CARD_W-180)
        draw_centered_lines(draw,(90,648,CARD_W-90,735),[group_txt],font_group,(220,228,245,235),line_spacing=4)
    channel_txt=ellipsize(draw,channel_txt,font_channel,380)
    ch_bbox=draw.textbbox((0,0),channel_txt,font=font_channel); ch_w=(ch_bbox[2]-ch_bbox[0])+48; left=(CARD_W-ch_w)//2
    draw.rounded_rectangle((left,810,left+ch_w,860), radius=22, fill=(0,0,0,175)); draw.text((left+24,824),channel_txt,font=font_channel,fill=(255,255,255,255))
    card_path=CARDS_DIR / f"{uid}.png"; img.convert("RGB").save(card_path, format="PNG", optimize=True)

    bg=Image.new("RGBA",(BG_W,BG_H),style["bg1"]+(255,))
    overlay=rounded_gradient_background((BG_W,BG_H),style["bg1"],style["bg2"]); overlay.putalpha(255); bg.alpha_composite(overlay)
    glow=Image.new("RGBA",(BG_W,BG_H),(0,0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse((-120,-140,680,280), fill=(255,255,255,18)); gd.ellipse((820,180,1500,860), fill=(255,255,255,10)); gd.rectangle((0,0,BG_W,BG_H), fill=(0,0,0,92))
    glow=glow.filter(ImageFilter.GaussianBlur(34)); bg.alpha_composite(glow)
    draw=ImageDraw.Draw(bg); draw.rounded_rectangle((68,BG_H-72,540,BG_H-58), radius=6, fill=tuple(style["accent"]))
    bg_label=get_font(22,True); bg_time=get_font(28,True); bg_title=get_font(76,True); bg_group=get_font(34,False); bg_channel=get_font(26,True); bg_badge=get_font(22,True)
    draw_badge(draw,42,34,style["label"],(255,255,255),(0,0,0),bg_label)
    if time_txt:
        time_bbox=draw.textbbox((0,0),time_txt,font=bg_time); tw=max(100,(time_bbox[2]-time_bbox[0])+28)
        draw_badge(draw,BG_W-tw-44,34,time_txt,(255,255,255),(0,0,0),bg_time)
    title_lines=fit_title_lines(draw,match_txt,bg_title,max_width=820,max_lines=3)
    draw_centered_lines(draw,(72,140,900,430),title_lines,bg_title,(255,255,255,255),line_spacing=8)
    if group_txt:
        group_txt=ellipsize(draw,group_txt,bg_group,790)
        draw_centered_lines(draw,(86,452,900,522),[group_txt],bg_group,(220,228,245,240),line_spacing=4)
    draw.rounded_rectangle((86,560,440,612), radius=22, fill=(0,0,0,170))
    channel_txt=ellipsize(draw,channel_txt,bg_channel,310); draw.text((112,575),channel_txt,font=bg_channel,fill=(255,255,255,255))
    logo_done=False
    if badge.get("file"):
        lp=CHANNEL_LOGOS_DIR / badge["file"]
        if lp.exists(): paste_channel_logo(bg, lp, 1010,78,180,80); logo_done=True
    draw=ImageDraw.Draw(bg)
    if not logo_done: draw_badge(draw,1000,86,badge["text"],tuple(badge["bg"]),tuple(badge["fg"]),bg_badge,tuple(style["accent"]))
    backdrop_path=BACKDROPS_DIR / f"{uid}_bg.png"; bg.convert("RGB").save(backdrop_path, format="PNG", optimize=True)
    return card_path.name, backdrop_path.name
def parse_attrs(line):
    attrs={}
    for k,v in re.findall(r'([a-zA-Z0-9\-_]+)="([^"]*)"', line): attrs[k]=v
    return attrs
def build():
    cfg=load_config(); base_url=cfg["base_url"].rstrip("/"); playlist_name=cfg.get("playlist_name","eventos_acestream_hosting_pro.m3u")
    raw=SOURCE_M3U.read_text(encoding="utf-8", errors="ignore").splitlines(); out_lines=["#EXTM3U"]
    CARDS_DIR.mkdir(parents=True, exist_ok=True); BACKDROPS_DIR.mkdir(parents=True, exist_ok=True)
    i=0
    while i < len(raw):
        line=raw[i].rstrip("\n")
        if line.startswith("#EXTINF"):
            attrs=parse_attrs(line); display_name=line.split(",",1)[1] if "," in line else ""; group_title=attrs.get("group-title",""); tvg_name=attrs.get("tvg-name","")
            uid=hash_id(group_title,tvg_name,display_name); card_name,bg_name=make_card_and_backdrop(uid,group_title,tvg_name,display_name)
            attrs["tvg-id"]=attrs.get("tvg-id", normalize_channel(tvg_name).replace(" ","."))
            attrs["tvg-logo"]=f"{base_url}/cards/{card_name}"; attrs["tvg-background"]=f"{base_url}/backdrops/{bg_name}"
            ordered=["tvg-id","tvg-name","tvg-logo","tvg-background","group-title"]; parts=[]
            for k in ordered:
                if attrs.get(k): parts.append(f'{k}="{attrs[k]}"')
            for k,v in attrs.items():
                if k not in ordered and v: parts.append(f'{k}="{v}"')
            out_lines.append(f'#EXTINF:-1 {" ".join(parts)},{display_name}')
            if i+1 < len(raw): out_lines.append(raw[i+1].rstrip("\n")); i+=2; continue
        elif line and line != "#EXTM3U": out_lines.append(line)
        i+=1
    (ROOT / playlist_name).write_text("\n".join(out_lines)+"\n", encoding="utf-8")
    print(f"OK: {ROOT / playlist_name}")
if __name__ == "__main__":
    build()
