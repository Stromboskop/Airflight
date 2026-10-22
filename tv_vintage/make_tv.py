"""Génère les STL de la TV vintage Airflight (mm).
Repère: x=largeur, y=profondeur (face avant y=0), z=hauteur (0 = centre du boîtier).
Carte écran 2.4" RPi Display (76 x 51 mm) avec boutons K1..K3 sur le bord gauche.
"""
import os
import numpy as np
import trimesh
from trimesh.creation import box, cylinder, cone

# ===================== PARAMÈTRES À RÉGLER =====================
# Hauteur des 3 boutons K1, K2, K3: distance (mm) depuis le BORD HAUT de la carte
# (mesuré sur la photo: ~12, 26, 40 mm). Modifie ici si les trous ne tombent pas pile.
BTN_SPACING = 7.8            # espace entre deux boutons (bord à bord)
BTN_Z_PITCH = BTN_SPACING + 6.0   # entraxe = espace + hauteur du bouton; K2 au centre de la carte
BTN_Z_OFFSET = 0.0           # >0 remonte les 3 boutons, <0 les descend
BTN_Z_FROM_TOP = None        # ou liste manuelle [K1, K2, K3] en mm depuis le bord haut de la carte
LEG_TILT_DEG = 12.0          # inclinaison des pieds vers l'extérieur (0 = droits)
BTN_W, BTN_H = 3.5, 6.0      # taille réelle des boutons (x, z)
BTN_CLEAR = 0.3              # jeu autour des boutons
BTN_HOLE_W = BTN_W + BTN_CLEAR
BTN_HOLE_H = BTN_H + BTN_CLEAR
BTN_GAP_TO_GLASS = 1.8       # bord du bouton -> bord de la dalle
PICO_SHIFT = 8.0             # plots du Pico rapprochés du centre du couvercle (x et z)
LEG_LEN = 70.0               # longueur des pieds
LEG_TIP_R = 2.5              # rayon du bout tronqué des pieds

CARD_W, CARD_H = 76.0, 51.0  # carte écran
GLASS_W, GLASS_H = 58.5, 44.5  # dalle visible (fenêtre), réduite de 3 mm côté opposé aux boutons
GLASS_DX, GLASS_DZ = -0.3, 3.0  # décalage du centre de la dalle / centre carte (+x droite, +z haut)

MARGIN_L = 10.0              # espace entre carte et paroi gauche (intérieur)
MARGIN_R = 10.0              # espace entre carte et paroi droite (1 cm)
MARGIN_TB = 14.0             # espace haut / bas
D = 78.0                     # profondeur (câbles Dupont ~40 mm derrière la carte)
T = 2.0                      # parois
FRONT = 1.2                  # épaisseur façade (fine pour que les boutons dépassent)
# ===============================================================

W = CARD_W + MARGIN_L + MARGIN_R + 2 * T
H = CARD_H + 2 * MARGIN_TB + 2 * T
CX = (MARGIN_L - MARGIN_R) / 2.0   # centre de la carte (repère boîtier)
CZ = 0.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")
os.makedirs(OUT, exist_ok=True)


def bx(sx, sy, sz, cx, cy, cz):
    return box(extents=(sx, sy, sz)).apply_translation((cx, cy, cz))


def cyl_y(r, length, cx, cy0, cz, sections=48):
    c = cylinder(radius=r, height=length, sections=sections)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (1, 0, 0)))
    return c.apply_translation((cx, cy0 + length / 2, cz))


def cyl_z(r, h, cx, cy, cz, sections=32):
    return cylinder(radius=r, height=h, sections=sections).apply_translation((cx, cy, cz))


def cyl_x(r, length, cx, sections=32):
    c = cylinder(radius=r, height=length, sections=sections)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (0, 1, 0)))
    return c.apply_translation((cx, 0, 0))


def frustum_x(r0, r1, x0, length, sections=32):
    prof = [(0, 0), (r0, 0), (r1, length), (0, length)]
    m = trimesh.creation.revolve(prof, sections=sections)   # axe z
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (0, 1, 0)))
    return m.apply_translation((x0, 0, 0))


def union(*m):
    return trimesh.boolean.union(list(m), engine="manifold")


def diff(a, *m):
    return trimesh.boolean.difference([a] + list(m), engine="manifold")


def save(m, name):
    m.export(os.path.join(OUT, name))
    print(name, "etanche:", m.is_watertight, "dim:", np.round(m.extents, 1))


# ---------- Boîtier (ouvert à l'arrière) ----------
body = bx(W, D, H, 0, D / 2, 0)
body = diff(body, bx(W - 2 * T, D - FRONT + 1, H - 2 * T, 0, FRONT + (D - FRONT + 1) / 2, 0))

# fenêtre de la dalle
body = diff(body, bx(GLASS_W, 10, GLASS_H, CX + GLASS_DX, 0, CZ + GLASS_DZ))

# grille de haut-parleur (côté opposé aux boutons), à droite du bord de la carte
GRILLE_W, GRILLE_SLOT_H, GRILLE_PITCH, GRILLE_N = 7.0, 1.6, 3.6, 11
GRILLE_X = CX + CARD_W / 2 + (W / 2 - T - CARD_W / 2 - CX) / 2
for i in range(GRILLE_N):
    gz = (i - (GRILLE_N - 1) / 2) * GRILLE_PITCH
    body = diff(body, bx(GRILLE_W, 10, GRILLE_SLOT_H, GRILLE_X, 0, CZ + gz))

# trous des 3 boutons de la carte (appui direct au doigt)
card_left = CX - CARD_W / 2
card_top = CZ + CARD_H / 2
glass_left = CX + GLASS_DX - GLASS_W / 2
BTN_X = glass_left - BTN_GAP_TO_GLASS - BTN_W / 2   # axe des boutons (repère boîtier)
if BTN_Z_FROM_TOP is None:
    BTN_Z_FROM_TOP = [CARD_H / 2 - GLASS_DZ - BTN_Z_OFFSET + k * BTN_Z_PITCH for k in (-1, 0, 1)]   # K2 centré sur la dalle
for zt in BTN_Z_FROM_TOP:
    body = diff(body, bx(BTN_HOLE_W, 10, BTN_HOLE_H, BTN_X, 0, card_top - zt))

# ouverture USB du Pico (paroi droite)
body = diff(body, bx(T * 3, 14, 9, W / 2, D - 22, -(H / 2 - T - 14) + PICO_SHIFT))
# douilles des pieds
LEG_X = W / 2 - 14
for sx in (-LEG_X, LEG_X):
    for sy in (14, D - 14):
        a = np.radians(LEG_TILT_DEG)
        d = np.array([np.sign(sx) * np.sin(a) / np.sqrt(2),
                      np.sign(sy - D / 2) * np.sin(a) / np.sqrt(2), -np.cos(a)])
        rot = np.eye(4)
        rot[:3, :3] = trimesh.geometry.align_vectors([0, 0, 1], d)[:3, :3]
        P = (sx, sy, -H / 2)
        boss = cylinder(radius=7, height=28, sections=32).apply_transform(rot).apply_translation(P)
        boss = diff(boss, bx(100, 100, 40, sx, sy, -H / 2 - 20))   # rien sous le plancher
        hole = cylinder(radius=4.2, height=24, sections=32).apply_transform(rot).apply_translation(P)
        body = diff(union(body, boss), hole)
# trou d'antenne
body = diff(body, cyl_z(3.2, T * 3, 0, D / 2, H / 2, 24))
# bossages de vis de fermeture
SX, SZ = W / 2 - T - 4, H / 2 - T - 4
for sx in (-SX, SX):
    for sz in (-SZ, SZ):
        body = union(body, cyl_y(4, 10, sx, D - 10, sz, 24))
        body = diff(body, cyl_y(1.1, 11, sx, D - 11, sz, 16))
save(body, "boitier.stl")

# ---------- Couvercle arrière (imprimé à plat) ----------
lid = bx(W - 2 * T - 0.6, 3, H - 2 * T - 0.6, 0, 1.5, 0)
for sx in (-SX, SX):
    for sz in (-SZ, SZ):
        lid = diff(lid, cyl_y(1.8, 5, sx, -1, sz, 16))
for i in range(5):                                                   # aération
    lid = diff(lid, bx(30, 6, 1.5, -10, 1.5, 12 - i * 4))
PICO_CX = W / 2 - T - 26 - PICO_SHIFT                                # plots Pico (M2, 47 x 11.4)
PICO_CZ = -(H / 2 - T - 14) + PICO_SHIFT
for dx in (-23.5, 23.5):
    for dz in (-5.7, 5.7):
        st = cyl_y(2.6, 6, PICO_CX + dx, 3, PICO_CZ + dz, 20)
        lid = union(lid, diff(st, cyl_y(0.9, 7, PICO_CX + dx, 3, PICO_CZ + dz, 12)))
lid.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, (1, 0, 0)))
save(lid, "couvercle.stl")

# ---------- Pied fuselé (x4) ----------
# cône prolongé puis tronqué à LEG_LEN (bout plat), avec coupe inclinée pour poser à plat malgré l'angle
full_len = LEG_LEN * 6.0 / (6.0 - LEG_TIP_R)
leg = cone(radius=6, height=full_len, sections=32).apply_transform(
    trimesh.transformations.rotation_matrix(np.pi, (1, 0, 0)))
a = np.radians(LEG_TILT_DEG)
n = np.array([np.sin(a), 0.0, np.cos(a)])        # normale du sol dans le repère du pied
cutter = box(extents=(300, 300, 300))
cutter.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], n))
cutter.apply_translation(n * (-LEG_LEN * np.cos(a)) - n * 150)
leg = diff(leg, cutter)
save(union(leg, cyl_z(4, 10, 0, 0, 5)), "pied_x4.stl")

# ---------- Base d'antenne ----------
ANT_HOLE_R = 2.2             # trous d'enfichage (pion de l'antenne = 2.0 mm de rayon)
ANT_HOLE_DEPTH = 9.0
ANT_SPLAY_DEG = 20.0         # écartement en V des deux antennes
ANT_HOLE_X = 6.0

base = union(cyl_z(14, 8, 0, 0, 4, 48), cyl_z(3, 10, 0, 0, -3, 24))
dome = trimesh.creation.icosphere(radius=14, subdivisions=3)
dome = diff(dome, bx(40, 40, 20, 0, 0, -10)).apply_scale((1, 1, 0.3)).apply_translation((0, 0, 8))
base = union(base, dome)
for s in (-1, 1):
    top = np.array([s * ANT_HOLE_X, 0, 12.0])
    d = np.array([s * np.sin(np.radians(ANT_SPLAY_DEG)), 0, np.cos(np.radians(ANT_SPLAY_DEG))])
    rot = np.eye(4)
    rot[:3, :3] = trimesh.geometry.align_vectors([0, 0, 1], d)[:3, :3]
    hole = cylinder(radius=ANT_HOLE_R, height=2 * ANT_HOLE_DEPTH, sections=24)
    base = diff(base, hole.apply_transform(rot).apply_translation(top))
save(base, "base_antenne.stl")

# ---------- Antennes (x2), télescopiques, à plat sur l'axe x ----------
# pion d'enfichage (x<0), brins de diamètre décroissant avec bagues, disque plat au bout
parts = [cyl_x(2.0, 9, -4.5, 24)]
x = 0.0
for r, ln in ((3.0, 26), (2.4, 22), (1.8, 20), (1.2, 20)):
    parts.append(cyl_x(r, ln, x + ln / 2, 32))
    parts.append(cyl_x(r + 0.7, 2.0, x + 1.0, 32))      # bague de jonction
    x += ln
# transition évasée par paliers vers le disque; chaque cône <= 40° (impression sans support)
parts.append(frustum_x(1.2, 1.8, x, 1.0))
parts.append(cyl_x(1.8, 0.6, x + 1.3, 32))
parts.append(frustum_x(1.8, 2.5, x + 1.6, 1.2))
x += 2.8
parts.append(cyl_x(2.5, 1.5, x + 0.75, 32))              # disque plat de bout (5 mm), perpendiculaire à l'antenne
save(union(*parts), "antenne_x2.stl")
