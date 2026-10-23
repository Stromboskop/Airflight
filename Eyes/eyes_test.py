# Run temporarily from the PC with: python -m mpremote connect COM4 run --no-follow eyes_test.py
from machine import Pin, SPI
import framebuf
import math
import random
import time
import ili9341


W, H = 320, 240
SPI_BAUDRATE = 40_000_000


def rgb(r, g, b):
    color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((color & 0xFF) << 8) | (color >> 8)


BACKGROUND = rgb(28, 17, 18)
SKIN_TOP = (108, 65, 55)
SKIN_BOTTOM = (168, 111, 89)
SKIN_LIGHT = rgb(197, 144, 116)
SKIN_DARK = rgb(76, 43, 40)
SCLERA = rgb(241, 233, 218)
SCLERA_EDGE = rgb(209, 197, 180)
IRIS_OUTER = rgb(37, 58, 49)
IRIS_MID = rgb(45, 111, 91)
IRIS_INNER = rgb(114, 145, 91)
IRIS_FIBER = rgb(157, 173, 117)
PUPIL = rgb(9, 15, 14)
HIGHLIGHT = rgb(255, 255, 247)
LASH_COLOR = rgb(76, 43, 40)

CX, CY = W // 2, H // 2
EYE_HALF_WIDTH = 126
EYE_HALF_HEIGHT = 77
fb = framebuf.FrameBuffer(bytearray(W * H * 2), W, H, framebuf.RGB565)


def draw_background():
    fb.fill(BACKGROUND)
    for y in range(H):
        blend = y / (H - 1)
        edge = abs(y - CY) / CY
        shade = 1.0 - 0.30 * edge
        r = int((SKIN_TOP[0] * (1 - blend) + SKIN_BOTTOM[0] * blend) * shade)
        g = int((SKIN_TOP[1] * (1 - blend) + SKIN_BOTTOM[1] * blend) * shade)
        b = int((SKIN_TOP[2] * (1 - blend) + SKIN_BOTTOM[2] * blend) * shade)
        fb.hline(0, y, W, rgb(r, g, b))


def eye_width_at(dy, half_height):
    if half_height <= 0 or abs(dy) >= half_height:
        return 0
    return int(EYE_HALF_WIDTH * math.sqrt(1 - (dy / half_height) ** 2))


def draw_eye_shape(half_height):
    for dy in range(-half_height, half_height + 1):
        width = eye_width_at(dy, half_height)
        if width:
            y = CY + dy
            fb.hline(CX - width, y, width * 2 + 1, SCLERA)
            edge_color = SCLERA_EDGE if abs(dy) > half_height * 0.72 else SCLERA
            fb.pixel(CX - width, y, edge_color)
            fb.pixel(CX + width, y, edge_color)

    fb.ellipse(CX, CY, EYE_HALF_WIDTH, max(1, half_height), SKIN_DARK)
    fb.ellipse(CX, CY, EYE_HALF_WIDTH - 2, max(1, half_height - 2), SCLERA_EDGE)


def draw_iris(gaze_x, gaze_y, half_height):
    radius = min(41, max(3, int(41 * min(1.0, half_height / 62))))
    max_x = EYE_HALF_WIDTH - radius - 5
    max_y = max(0, half_height - int(radius * 0.62))
    ix = CX + max(-max_x, min(max_x, int(gaze_x)))
    iy = CY + max(-max_y, min(max_y, int(gaze_y)))

    fb.ellipse(ix, iy, radius, radius, IRIS_OUTER, True)
    fb.ellipse(ix, iy, int(radius * 0.84), int(radius * 0.84), IRIS_MID, True)
    fb.ellipse(ix, iy, int(radius * 0.58), int(radius * 0.58), IRIS_INNER, True)

    for i in range(40):
        angle = (i * 2.0 * math.pi / 40) + 0.06 * math.sin(i * 1.7)
        inner = radius * (0.42 + 0.08 * (i % 3))
        outer = radius * (0.90 + 0.06 * math.sin(i * 2.3))
        color = IRIS_FIBER if i % 3 else IRIS_OUTER
        x0 = int(ix + math.cos(angle) * inner)
        y0 = int(iy + math.sin(angle) * inner)
        x1 = int(ix + math.cos(angle) * outer)
        y1 = int(iy + math.sin(angle) * outer)
        fb.line(x0, y0, x1, y1, color)

    fb.ellipse(ix, iy, int(radius * 0.39), int(radius * 0.39), IRIS_OUTER, True)
    pupil_radius = max(2, int(radius * 0.31))
    fb.ellipse(ix, iy, pupil_radius, pupil_radius, PUPIL, True)
    fb.ellipse(ix - radius // 3, iy - radius // 3, max(2, radius // 7),
               max(2, radius // 7), HIGHLIGHT, True)
    fb.ellipse(ix + radius // 4, iy + radius // 5, max(1, radius // 12),
               max(1, radius // 12), HIGHLIGHT, True)


def draw_lids(half_height):
    for dy in range(-half_height, half_height + 1):
        width = eye_width_at(dy, half_height)
        if not width:
            continue
        y = CY + dy
        fb.pixel(CX - width, y, SKIN_DARK)
        fb.pixel(CX + width, y, SKIN_DARK)

    fold_height = max(2, int(half_height * 0.22))
    for x in range(CX - EYE_HALF_WIDTH + 10, CX + EYE_HALF_WIDTH - 9, 2):
        normalized = (x - CX) / EYE_HALF_WIDTH
        curve = math.sqrt(max(0, 1 - normalized * normalized))
        upper = CY - int(half_height * curve)
        fb.pixel(x, max(0, upper - fold_height), SKIN_LIGHT)
        fb.pixel(x, max(0, upper - fold_height - 1), SKIN_DARK)

    fb.ellipse(CX, CY, EYE_HALF_WIDTH + 2, max(2, half_height + 2), SKIN_DARK)
    fb.ellipse(CX, CY, EYE_HALF_WIDTH, max(1, half_height), SKIN_LIGHT)


def draw_lashes(half_height):
    lash_color = LASH_COLOR
    for index, x in enumerate(range(CX - 108, CX + 109, 11)):
        normalized = (x - CX) / EYE_HALF_WIDTH
        curve = math.sqrt(max(0, 1 - normalized * normalized))
        root_y = CY - int(half_height * curve)
        length = max(1, int((5 + index % 4) * min(1.0, half_height / 40)))
        direction = -1 if x < CX else 1
        tip_x = x + direction * (1 + index % 3)
        fb.line(x, root_y, tip_x, root_y - length, lash_color)


def render(gaze_x, gaze_y, openness):
    draw_background()
    half_height = max(2, int(EYE_HALF_HEIGHT * openness))
    draw_eye_shape(half_height)
    draw_iris(gaze_x, gaze_y, half_height)
    draw_lids(half_height)
    draw_lashes(half_height)


def main():
    spi = SPI(0, baudrate=SPI_BAUDRATE, sck=Pin(18), mosi=Pin(19), miso=Pin(16))
    display = ili9341.ILI9341(
        spi,
        dc=Pin(22, Pin.OUT),
        cs=Pin(17, Pin.OUT),
        rst=Pin(21, Pin.OUT),
    )

    gaze_x = 0.0
    gaze_y = 0.0
    target_x = 0.0
    target_y = 0.0
    next_gaze = time.ticks_ms()
    next_blink = time.ticks_add(next_gaze, random.randint(2800, 6000))
    blink_started = None
    double_blink = False

    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, next_gaze) >= 0:
            target_x = random.uniform(-52, 52)
            target_y = random.uniform(-19, 19)
            next_gaze = time.ticks_add(now, random.randint(650, 1700))

        gaze_x += (target_x - gaze_x) * 0.24
        gaze_y += (target_y - gaze_y) * 0.24

        if blink_started is None and time.ticks_diff(now, next_blink) >= 0:
            blink_started = now

        openness = 1.0
        if blink_started is not None:
            elapsed = time.ticks_diff(now, blink_started)
            if elapsed < 65:
                openness = max(0.04, 1 - elapsed / 65)
            elif elapsed < 100:
                openness = 0.04
            elif elapsed < 190:
                openness = min(1.0, 0.04 + (elapsed - 100) / 90 * 0.96)
            else:
                blink_started = None
                if not double_blink and random.random() < 0.12:
                    next_blink = time.ticks_add(now, random.randint(240, 380))
                    double_blink = True
                else:
                    next_blink = time.ticks_add(now, random.randint(2800, 6000))
                    double_blink = False

        render(gaze_x, gaze_y, openness)
        display.blit(fb, 0, 0, W, H)
        time.sleep_ms(30)


main()
