# Airflight - Pico 2 W + écran 2.4" RPi Display (ILI9341 320x240, tactile XPT2046)

Brochage complet : voir [pinout.csv](./pinout.csv). Résumé (écran et tactile partagent SCK/MOSI) :

| Broche écran | Signal | Pico 2 (GPIO) | Broche physique |
| --- | --- | --- | --- |
| 1 / 17 | 3,3 V | 3V3(OUT) | 36 |
| 6, 9, 14, 20, 25 | GND | GND | 23 par ex. |
| 19 | MOSI | GP19 | 25 |
| 21 | MISO (tactile) | GP16 | 21 |
| 23 | SCK | GP18 | 24 |
| 24 | LCD_CS | GP17 | 22 |
| 26 | TP_CS | GP20 | 26 |
| 15 | DC (LCD_RS) | GP22 | 29 |
| 13 | RESET | GP21 | 27 |
| 11 | TP_IRQ | GP15 | 20 |

## Boutons (KEY1/2/3, reliés à la masse, résistance pull-up interne du Pico)

| Bouton | Broche écran | Pico 2 | Broche physique | Rôle |
| --- | --- | --- | --- | --- |
| KEY1 | 12 | GP14 | 19 | Avion suivant (retour au premier après le dernier) |
| KEY2 | 16 | GP13 | 17 | Page de détails : compagnie, nationalité, heures estimées |
| KEY3 | 18 | GP12 | 16 | Surface affichée : 15, 30, 45 NM puis retour à 15 |

Le tactile sélectionne un avion en le touchant sur le radar.
Les mentions P0, P1... sur l'écran ne correspondent pas aux GPIO du Pico.
Rétro-éclairage non piloté (toujours allumé). Si trop faible : 5 V (broche 2/4) sur VBUS (40).

## API (gratuites, sans clé)
- Positions : `https://api.adsb.lol/v2/point/{lat}/{lon}/{rayon_NM}` (rayon fixé à 45 NM, le zoom recadre)
- Trajet par indicatif : `https://api.adsbdb.com/v0/callsign/{indicatif}`

## Installation
1. Flasher MicroPython pour Pico 2 W.
2. Éditer `secrets.py` (WiFi, latitude, longitude, `TZ_OFFSET_HOURS`).
3. Copier `main.py`, `ili9341.py`, `xpt2046.py`, `secrets.py` sur le Pico.
4. Les échelles se règlent dans `SCALES_NM` en tête de `main.py`.

Si le tactile est décalé ou inversé, ajuster `xmin/xmax/ymin/ymax/swap` dans `xpt2046.py`.
