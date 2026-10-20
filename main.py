# pyright: reportMissingImports=false
# Radar des avions au-dessus du domicile (ecran 320x240)
# Positions : adsb.lol - Trajet : adsbdb.com
from machine import Pin, SPI
import network
import time
import math
import framebuf
import ntptime
from array import array

try:
    import urequests as requests
except ImportError:
    import requests

import ili9341
from xpt2046 import XPT2046
import secrets

# --- Branchements (voir BRANCHEMENTS.md) ---
spi = SPI(0, baudrate=40_000_000, sck=Pin(18), mosi=Pin(19), miso=Pin(16))
tft = ili9341.ILI9341(spi, dc=Pin(22, Pin.OUT), cs=Pin(17, Pin.OUT), rst=Pin(21, Pin.OUT))
touch = XPT2046(spi, cs=Pin(20, Pin.OUT), irq=Pin(15, Pin.IN, Pin.PULL_UP))
# Boutons relies a la masse : appui = 0
KEY_NEXT = Pin(14, Pin.IN, Pin.PULL_UP)    # KEY1 : avion suivant
KEY_DETAIL = Pin(13, Pin.IN, Pin.PULL_UP)  # KEY2 : page details
KEY_SCALE = Pin(12, Pin.IN, Pin.PULL_UP)   # KEY3 : echelle
TZ_OFFSET = getattr(secrets, "TZ_OFFSET_HOURS", 2)

# Tampon complet 320x240 (150 Ko) envoye d'un bloc : pas de scintillement
W, H = 320, 240
fb = framebuf.FrameBuffer(bytearray(W * H * 2), W, H, framebuf.RGB565)


def rgb(r, g, b):
    """RGB565 avec octets inverses (le bus SPI attend du big-endian)."""
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


BLACK = rgb(0, 0, 0)
WHITE = rgb(255, 255, 255)
YELLOW = rgb(255, 220, 0)
CYAN = rgb(0, 220, 255)
GREEN = rgb(0, 255, 100)
RED = rgb(255, 60, 60)
GREY = rgb(120, 120, 120)
DKGREEN = rgb(0, 70, 30)
ORANGE = rgb(255, 150, 0)

# Radar : cercle de 224 px (x 6..230, y 8..232) ; panneau d'infos x 238..319
CX, CY, R = 118, 120, 112
PANEL_X = 238
HOME_LAT = secrets.LATITUDE
HOME_LON = secrets.LONGITUDE
SCALES_NM = (15, 30, 45)
scale_idx = 0
PX_PER_KM = R / (SCALES_NM[0] * 1.852)


def set_scale(i):
    global scale_idx, PX_PER_KM
    scale_idx = i
    PX_PER_KM = R / (SCALES_NM[i] * 1.852)
KM_PER_DEG = 111.32
TRAIL_POINTS = 6
PREDICT_MIN = 3

route_cache = {}
history = {}


def clean(s):
    table = {"é": "e", "è": "e", "ê": "e", "ë": "e", "à": "a", "â": "a", "ô": "o",
             "î": "i", "ï": "i", "ç": "c", "ü": "u", "ö": "o", "ä": "a", "ñ": "n",
             "É": "E", "Ö": "O", "Ü": "U", "ú": "u", "ó": "o", "í": "i", "á": "a"}
    return "".join(table.get(c, c) if ord(c) > 127 else c for c in str(s))


def big_text(x, y, s, color, scale):
    s = clean(s)
    mono = framebuf.FrameBuffer(bytearray(len(s) * 8), len(s) * 8, 8, framebuf.MONO_HLSB)
    mono.text(s, 0, 0, 1)
    for row in range(8):
        for col in range(len(s) * 8):
            if mono.pixel(col, row):
                fb.fill_rect(x + col * scale, y + row * scale, scale, scale, color)


def message(title, detail="", color=WHITE):
    fb.fill(BLACK)
    big_text(10, 90, title[:13], color, 3)
    if detail:
        fb.text(clean(detail)[:38], 10, 140, GREY)
    tft.blit(fb, 0, 0, W, H)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    nets = []
    if getattr(secrets, "LIVEBOX_WIFI_SSID", ""):
        nets.append((secrets.LIVEBOX_WIFI_SSID, secrets.LIVEBOX_WIFI_PASSWORD))
    nets.append((secrets.WIFI_SSID, secrets.WIFI_PASSWORD))
    for ssid, pwd in nets:
        message("WiFi...", ssid)
        wlan.connect(ssid, pwd)
        t0 = time.ticks_ms()
        while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 20000:
            time.sleep_ms(250)
        if wlan.isconnected():
            return wlan
        wlan.disconnect()
    return None


def get_json(url):
    r = requests.get(url, headers={"User-Agent": "airflight-pico"})
    try:
        if r.status_code != 200:
            raise RuntimeError("HTTP %d" % r.status_code)
        return r.json()
    finally:
        r.close()


def to_km(lat, lon):
    """Position relative au domicile : (est, nord) en km."""
    return ((lon - HOME_LON) * math.cos(math.radians(HOME_LAT)) * KM_PER_DEG,
            (lat - HOME_LAT) * KM_PER_DEG)


def fetch_aircraft():
    # On charge toujours la plus grande echelle ; le zoom ne fait que recadrer
    url = "https://opendata.adsb.fi/api/v3/lat/%s/lon/%s/dist/%s" % (
        HOME_LAT, HOME_LON, max(SCALES_NM))
    data = get_json(url)
    if not isinstance(data, dict):
        raise ValueError("Reponse API invalide")
    aircraft = data.get("ac")
    if not isinstance(aircraft, list):
        raise ValueError("Champ ac invalide")
    planes, seen = [], set()
    for a in aircraft:
        alt = a.get("alt_baro")
        if "lat" not in a or "lon" not in a or alt == "ground":
            continue
        e, n = to_km(a["lat"], a["lon"])
        key = a.get("hex", "")
        seen.add(key)
        trail = history.setdefault(key, [])
        trail.append((e, n))
        del trail[:-TRAIL_POINTS]
        planes.append({
            "hex": key,
            "call": (a.get("flight") or "").strip(),
            "type": a.get("t", ""),
            "alt": int(alt) if isinstance(alt, (int, float)) else 0,
            "spd": int(a.get("gs", 0) or 0),
            "hdg": int(a.get("track", 0) or 0),
            "lat": a["lat"], "lon": a["lon"],
            "e": e, "n": n,
            "dist": math.sqrt(e * e + n * n),
        })
    for k in list(history):
        if k not in seen:
            del history[k]
    planes.sort(key=lambda p: p["dist"])
    return planes


def fetch_route(call):
    if not call:
        return None
    if call in route_cache:
        return route_cache[call]
    route = None
    try:
        data = get_json("https://api.adsbdb.com/v0/callsign/" + call)
        fr = ((data or {}).get("response") or {}).get("flightroute")
        if fr:
            route = {
                "airline": (fr.get("airline") or {}).get("name", ""),
                "country": (fr.get("airline") or {}).get("country", ""),
                "o_lat": fr["origin"].get("latitude"),
                "o_lon": fr["origin"].get("longitude"),
                "d_lat": fr["destination"].get("latitude"),
                "d_lon": fr["destination"].get("longitude"),
                "o_code": fr["origin"].get("iata_code", ""),
                "o_city": fr["origin"].get("municipality", ""),
                "d_code": fr["destination"].get("iata_code", ""),
                "d_city": fr["destination"].get("municipality", ""),
            }
    except Exception as e:
        print("route", e)
    if len(route_cache) > 40:
        route_cache.clear()
    route_cache[call] = route
    return route


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def hhmm(t):
    lt = time.localtime(int(t) + TZ_OFFSET * 3600)
    return "%02d:%02d" % (lt[3], lt[4])


def draw_details(p, route, total, idx):
    """Page detail : compagnie, nationalite, heures estimees (position + vitesse)."""
    fb.fill(BLACK)
    big_text(8, 6, p["call"] or "?", YELLOW, 3)
    fb.text("%d/%d" % (idx + 1, total), 270, 10, GREY)
    if not route:
        big_text(8, 100, "Trajet inconnu", RED, 2)
        return
    fb.text("Compagnie :", 8, 36, GREY)
    big_text(8, 48, route["airline"][:19], WHITE, 2)
    fb.text("Nationalite : %s" % clean(route["country"])[:22], 8, 70, ORANGE)
    big_text(8, 92, route["o_code"], CYAN, 3)
    fb.text(clean(route["o_city"])[:14], 8, 120, WHITE)
    fb.text("-->", 140, 100, GREY)
    big_text(190, 92, route["d_code"], GREEN, 3)
    fb.text(clean(route["d_city"])[:14], 190, 120, WHITE)
    if route["o_lat"] is None or route["d_lat"] is None:
        return
    done = haversine_km(route["o_lat"], route["o_lon"], p["lat"], p["lon"])
    left = haversine_km(p["lat"], p["lon"], route["d_lat"], route["d_lon"])
    pct = int(100 * done / (done + left)) if done + left else 0
    fb.rect(8, 138, 304, 10, GREY)
    fb.fill_rect(10, 140, 300 * pct // 100, 6, CYAN)
    if p["spd"] > 50:
        v = p["spd"] * 1.852
        now = time.time()
        fb.text("Depart ~", 8, 160, GREY)
        big_text(8, 172, hhmm(now - done / v * 3600), CYAN, 3)
        fb.text("Arrivee ~", 170, 160, GREY)
        big_text(170, 172, hhmm(now + left / v * 3600), GREEN, 3)
    fb.text("%d km restants  heure %s" % (left, hhmm(time.time())), 8, 214, GREY)


def screen_xy(e, n):
    return int(CX + e * PX_PER_KM), int(CY - n * PX_PER_KM)


def in_radar(x, y):
    return (x - CX) ** 2 + (y - CY) ** 2 <= R * R


def draw_north_arrow():
    """Fleche du nord (haut de l'ecran = nord), coin haut-gauche."""
    fb.line(18, 36, 18, 14, WHITE)
    fb.poly(0, 0, array("h", [18, 6, 13, 16, 23, 16]), WHITE, True)
    fb.text("N", 14, 40, WHITE)


PLANE_SHAPES = (
    ((10, 0), (6, 2), (-8, 1.5), (-8, -1.5), (6, -2)),      # fuselage
    ((2, 1), (-3, 9), (-5, 9), (-3, 1)),                    # aile droite
    ((2, -1), (-3, -9), (-5, -9), (-3, -1)),                # aile gauche
    ((-5, 1), (-8, 4.5), (-9, 4.5), (-8, 1)),               # stabilisateur droit
    ((-5, -1), (-8, -4.5), (-9, -4.5), (-8, -1)),           # stabilisateur gauche
)


def draw_plane(p, selected):
    x, y = screen_xy(p["e"], p["n"])
    if not in_radar(x, y):
        return
    color = YELLOW if selected else CYAN
    trail = history.get(p["hex"], [])
    for i in range(len(trail) - 1):
        x0, y0 = screen_xy(*trail[i])
        x1, y1 = screen_xy(*trail[i + 1])
        fb.line(x0, y0, x1, y1, GREY)
    # trajectoire prevue sur PREDICT_MIN minutes, par rapport au nord
    h = math.radians(p["hdg"])
    dx, dy = math.sin(h), -math.cos(h)
    km = p["spd"] * 1.852 * PREDICT_MIN / 60
    fb.line(x, y, int(x + dx * km * PX_PER_KM), int(y + dy * km * PX_PER_KM), color)
    # silhouette d'avion orientee selon le cap (f = vers l'avant, s = vers la droite)
    px, py = -dy, dx
    for shape in PLANE_SHAPES:
        pts = array("h")
        for f, s in shape:
            pts.append(int(x + dx * f + px * s))
            pts.append(int(y + dy * f + py * s))
        fb.poly(0, 0, pts, color, True)
    if selected:
        fb.ellipse(x, y, 11, 11, YELLOW)


def draw_panel(p, route, total, idx):
    x = PANEL_X + 2
    fb.vline(PANEL_X - 3, 0, H, GREY)
    fb.text(p["call"][:9] or "?", x, 4, YELLOW)
    fb.text("%d/%d" % (idx + 1, total), x, 16, GREY)
    if route:
        big_text(x, 34, route["o_code"], CYAN, 2)
        fb.text(clean(route["o_city"])[:10], x, 52, WHITE)
        fb.text("v", x + 20, 66, GREY)
        big_text(x, 80, route["d_code"], GREEN, 2)
        fb.text(clean(route["d_city"])[:10], x, 98, WHITE)
        fb.text(clean(route["airline"])[:10], x, 116, GREY)
    else:
        fb.text("Trajet", x, 50, RED)
        fb.text("inconnu", x, 62, RED)
    fb.text(p["type"][:10], x, 140, WHITE)
    fb.text("%dft" % p["alt"], x, 160, WHITE)
    fb.text("%dkt" % p["spd"], x, 176, WHITE)
    fb.text("%.1fkm" % p["dist"], x, 192, WHITE)
    fb.text("cap %d" % p["hdg"], x, 208, WHITE)


def draw(planes, sel_hex, mode=0):
    if mode == 1 and planes:
        i = [p["hex"] for p in planes].index(sel_hex)
        draw_details(planes[i], fetch_route(planes[i]["call"]), len(planes), i)
        tft.blit(fb, 0, 0, W, H)
        return
    fb.fill(BLACK)
    for k in (1, 2, 3):
        fb.ellipse(CX, CY, R * k // 3, R * k // 3, DKGREEN)
    fb.line(CX - R, CY, CX + R, CY, DKGREEN)
    fb.line(CX, CY - R, CX, CY + R, DKGREEN)
    fb.text("%dNM" % SCALES_NM[scale_idx], CX + 2, CY + R - 12, GREY)
    fb.fill_rect(CX - 2, CY - 2, 5, 5, GREEN)  # domicile
    draw_north_arrow()
    idx = 0
    for i, p in enumerate(planes):
        if p["hex"] == sel_hex:
            idx = i
    for i, p in enumerate(planes):
        if i != idx:
            draw_plane(p, False)
    if planes:
        draw_plane(planes[idx], True)
        draw_panel(planes[idx], fetch_route(planes[idx]["call"]), len(planes), idx)
    else:
        fb.text("Ciel vide", PANEL_X + 2, 100, GREY)
    tft.blit(fb, 0, 0, W, H)


def pick(planes, tx, ty, current_hex):
    """Avion le plus proche du doigt, sinon l'avion suivant."""
    best, bd = None, 30 * 30
    for p in planes:
        x, y = screen_xy(p["e"], p["n"])
        d = (x - tx) ** 2 + (y - ty) ** 2
        if d < bd:
            best, bd = p["hex"], d
    if best:
        return best
    hexes = [p["hex"] for p in planes]
    if current_hex in hexes:
        return hexes[(hexes.index(current_hex) + 1) % len(hexes)]
    return hexes[0] if hexes else None


def main():
    wlan = connect_wifi()
    if not wlan:
        message("Pas de WiFi", "Verifier secrets.py", RED)
        return
    try:
        ntptime.settime()
    except Exception as e:
        print("ntp", e)
    sel = None
    mode = 0
    while True:
        if not wlan.isconnected():
            wlan = connect_wifi()
            if not wlan:
                time.sleep(10)
                continue
        try:
            planes = fetch_aircraft()
        except Exception as e:
            print("fetch", e)
            message("Erreur reseau", str(e)[:30], RED)
            time.sleep(secrets.UPDATE_INTERVAL_SECONDS)
            continue
        if planes and sel not in [p["hex"] for p in planes]:
            sel = planes[0]["hex"]
        draw(planes, sel, mode)
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < secrets.UPDATE_INTERVAL_SECONDS * 1000:
            hexes = [p["hex"] for p in planes]
            changed = False
            if planes and sel in hexes and KEY_NEXT.value() == 0:
                sel, changed = hexes[(hexes.index(sel) + 1) % len(hexes)], True
            if KEY_DETAIL.value() == 0:
                mode, changed = 1 - mode, True
            if KEY_SCALE.value() == 0:
                set_scale((scale_idx + 1) % len(SCALES_NM))
                changed = True
            xy = touch.get_xy()
            if xy and planes and mode == 0:
                sel, changed = pick(planes, xy[0], xy[1], sel), True
            if changed:
                draw(planes, sel, mode)
                time.sleep_ms(300)
            time.sleep_ms(50)


main()
