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
BTN_Z_PITCH = 14.0           # écart régulier entre boutons; K2 est au centre de la carte
BTN_Z_OFFSET = 0.0           # >0 remonte les 3 boutons, <0 les descend
BTN_Z_FROM_TOP = None        # ou liste manuelle [K1, K2, K3] en mm depuis le bord haut de la carte
LEG_TILT_DEG = 12.0          # inclinaison des pieds vers l'extérieur (0 = droits)
BTN_X_FROM_LEFT = 2.5        # axe des boutons depuis le bord gauche de la carte
BTN_HOLE_W = 6.5             # trou: largeur (x)
BTN_HOLE_H = 9.0             # trou: hauteur (z)

CARD_W, CARD_H = 76.0, 51.0  # carte écran
GLASS_W, GLASS_H = 61.5, 44.5  # dalle visible (fenêtre)
GLASS_DX, GLASS_DZ = 1.2, 3.0  # décalage du centre de la dalle / centre carte (+x droite, +z haut)

MARGIN_L = 10.0              # espace entre carte et paroi gauche (intérieur)
MARGIN_R = 10.0              # espace entre carte et paroi droite (1 cm)
MARGIN_TB = 14.0             # espace haut / bas
D = 78.0                     # profondeur (câbles Dupont ~40 mm derrière la carte)
T = 3.0                      # parois
FRONT = 3.0                  # épaisseur façade
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

# trous des 3 boutons de la carte (appui direct au doigt)
card_left = CX - CARD_W / 2
card_top = CZ + CARD_H / 2
if BTN_Z_FROM_TOP is None:
    BTN_Z_FROM_TOP = [CARD_H / 2 - BTN_Z_OFFSET + k * BTN_Z_PITCH for k in (-1, 0, 1)]
for zt in BTN_Z_FROM_TOP:
    body = diff(body, bx(BTN_HOLE_W, 10, BTN_HOLE_H, card_left + BTN_X_FROM_LEFT, 0, card_top - zt))

# maintien de la carte: 4 languettes haut/bas (clip) + 4 butées latérales
LIP_Y0 = FRONT + 1.9              # PCB 1.6 mm + jeu
for sz in (+1, -1):
    for dx in (-20, 20):
        zc = CZ + sz * (CARD_H / 2)
        body = union(body, bx(14, 3.2, 2.0, CX + dx, FRONT + 1.6, zc + sz * 1.3))      # montant
        body = union(body, bx(14, 1.2, 2.6, CX + dx, LIP_Y0 + 0.6, zc + sz * (-0.1)))   # lèvre
for sx in (+1, -1):
    for dz in (-12, 12):
        body = union(body, bx(2.0, 5.0, 10, CX + sx * (CARD_W / 2 + 1.3), FRONT + 2.5, CZ + dz))

# ouverture USB du Pico (paroi droite)
body = diff(body, bx(T * 3, 14, 9, W / 2, D - 22, -(H / 2 - T - 14)))
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
        boss = cylinder(radius=7, height=20, sections=32).apply_transform(rot).apply_translation(P)
        boss = diff(boss, bx(100, 100, 40, sx, sy, -H / 2 - 20))   # rien sous le plancher
        hole = cylinder(radius=4.2, height=18, sections=32).apply_transform(rot).apply_translation(P)
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
PICO_CX, PICO_CZ = W / 2 - T - 26, -(H / 2 - T - 14)                # plots Pico (M2, 47 x 11.4)
for dx in (-23.5, 23.5):
    for dz in (-5.7, 5.7):
        st = cyl_y(2.6, 6, PICO_CX + dx, 3, PICO_CZ + dz, 20)
        lid = union(lid, diff(st, cyl_y(0.9, 7, PICO_CX + dx, 3, PICO_CZ + dz, 12)))
lid.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, (1, 0, 0)))
save(lid, "couvercle.stl")

# ---------- Pied fuselé (x4) ----------
leg = cone(radius=6, height=70, sections=32).apply_transform(
    trimesh.transformations.rotation_matrix(np.pi, (1, 0, 0)))
save(union(leg, cyl_z(4, 10, 0, 0, 5)), "pied_x4.stl")

# ---------- Base d'antenne ----------
base = union(cyl_z(14, 4, 0, 0, 2, 48), cyl_z(3, 10, 0, 0, -3, 24))
dome = trimesh.creation.icosphere(radius=14, subdivisions=3)
dome = diff(dome, bx(40, 40, 20, 0, 0, -10)).apply_scale((1, 1, 0.3))
save(union(base, dome), "base_antenne.stl")

# ---------- Antennes (x2) ----------
ant = cylinder(radius=1.5, height=110, sections=16)
ant.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (0, 1, 0)))
save(ant, "antenne_x2.stl")
