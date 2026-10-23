# Temporary USB test: python -m mpremote connect COM4 run --no-follow moods_test.py
from array import array
from machine import Pin, SPI
import framebuf
import math
import time
import ili9341


W, H = 320, 240
FRAME_MS = 60
MOOD_MS = 1900


def rgb(r, g, b):
    color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((color & 0xFF) << 8) | (color >> 8)


BG = rgb(255, 255, 255)
BODY = rgb(197, 222, 250)
BODY_EDGE = rgb(72, 112, 177)
NAVY = rgb(28, 20, 55)
CYAN = rgb(61, 232, 239)
WHITE = rgb(255, 255, 255)
fb = framebuf.FrameBuffer(bytearray(W * H * 2), W, H, framebuf.RGB565)


def rounded_rect(x, y, w, h, radius, color):
    fb.fill_rect(x + radius, y, w - 2 * radius, h, color)
    fb.fill_rect(x, y + radius, w, h - 2 * radius, color)
    for cx in (x + radius, x + w - radius):
        for cy in (y + radius, y + h - radius):
            fb.ellipse(cx, cy, radius, radius, color, True)


def outline_round_rect(x, y, w, h, radius, thickness, color, fill):
    rounded_rect(x, y, w, h, radius, color)
    rounded_rect(
        x + thickness, y + thickness, w - 2 * thickness, h - 2 * thickness,
        max(1, radius - thickness), fill
    )


def line(points, color):
    for i in range(len(points) - 1):
        fb.line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], color)


def filled_poly(points, color):
    coords = array("h")
    for x, y in points:
        coords.append(x)
        coords.append(y)
    fb.poly(0, 0, coords, color, True)


def draw_robot():
    fb.fill(BG)

    # Antenna and small side fins.
    fb.line(160, 78, 160, 43, BODY_EDGE)
    fb.line(157, 77, 157, 43, NAVY)
    fb.ellipse(160, 27, 10, 10, BODY_EDGE, True)
    fb.ellipse(160, 27, 7, 7, NAVY, True)
    filled_poly(((58, 164), (39, 179), (59, 185)), BODY_EDGE)
    filled_poly(((262, 164), (281, 179), (261, 185)), BODY_EDGE)
    filled_poly(((60, 166), (45, 178), (61, 181)), BODY)
    filled_poly(((260, 166), (275, 178), (259, 181)), BODY)

    outline_round_rect(49, 75, 222, 145, 51, 4, BODY_EDGE, BODY)


def draw_face_panel():
    outline_round_rect(88, 116, 144, 79, 28, 4, BODY_EDGE, NAVY)


def draw_smile(cx=160, cy=172, width=22):
    line(((cx - width // 2, cy), (cx - width // 4, cy + 4),
          (cx, cy + 5), (cx + width // 4, cy + 4),
          (cx + width // 2, cy)), WHITE)


def draw_frown(cx=160, cy=174, width=23):
    line(((cx - width // 2, cy + 4), (cx - width // 4, cy),
          (cx, cy - 2), (cx + width // 4, cy),
          (cx + width // 2, cy + 4)), WHITE)


def draw_heart(cx, cy, size):
    fb.ellipse(cx - size // 2, cy - size // 4, size // 2, size // 2, CYAN, True)
    fb.ellipse(cx + size // 2, cy - size // 4, size // 2, size // 2, CYAN, True)
    filled_poly(((cx - size, cy - size // 6),
                 (cx + size, cy - size // 6),
                 (cx, cy + size)), CYAN)


def draw_mood(mood, phase):
    draw_robot()
    draw_face_panel()
    pulse = int(2 * math.sin(phase * 5))

    if mood == 0:  # Happy
        fb.ellipse(132, 146 + pulse, 9, 10, CYAN, True)
        fb.ellipse(188, 146 + pulse, 9, 10, CYAN, True)
        draw_smile()
    elif mood == 1:  # Sad
        fb.ellipse(132, 147, 9, 10, CYAN, True)
        fb.ellipse(188, 147, 9, 10, CYAN, True)
        draw_frown(cy=175 + int(2 * math.sin(phase * 4)))
    elif mood == 2:  # Delighted / surprised
        fb.ellipse(132, 147, 9, 10, CYAN, True)
        fb.ellipse(188, 147, 9, 10, CYAN, True)
        fb.ellipse(160, 174, 12, 9 + int(2 * (1 + math.sin(phase * 6))), WHITE, True)
    elif mood == 3:  # Thinking
        for i in range(4):
            radius = 4 + (1 if int(phase * 5) % 4 == i else 0)
            fb.ellipse(132 + i * 19, 155, radius, radius, CYAN, True)
    elif mood == 4:  # Wink
        fb.ellipse(132, 146, 9, 10, CYAN, True)
        line(((181, 149), (188, 143), (195, 149)), CYAN)
        draw_smile(cy=174)
    elif mood == 5:  # In love
        draw_heart(132, 147, 11)
        draw_heart(188, 147, 11)
        draw_smile(cy=174)
    elif mood == 6:  # Angry
        fb.ellipse(132, 151, 10, 7, CYAN, True)
        fb.ellipse(188, 151, 10, 7, CYAN, True)
        line(((121, 137), (133, 141), (143, 145)), CYAN)
        line(((177, 145), (187, 141), (199, 137)), CYAN)
        fb.fill_rect(149, 174, 22, 3, WHITE)
    elif mood == 7:  # Kiss
        line(((122, 147), (128, 151), (136, 151), (142, 147)), CYAN)
        line(((178, 147), (184, 151), (192, 151), (198, 147)), CYAN)
        fb.ellipse(160, 174, 7, 8, CYAN, True)
    else:  # Dizzy
        for cx in (132, 188):
            line(((cx - 8, 139), (cx + 8, 155)), CYAN)
            line(((cx + 8, 139), (cx - 8, 155)), CYAN)
        fb.ellipse(160, 174, 8, 10, WHITE, True)


def main():
    spi = SPI(0, baudrate=40_000_000, sck=Pin(18), mosi=Pin(19), miso=Pin(16))
    display = ili9341.ILI9341(
        spi, dc=Pin(22, Pin.OUT), cs=Pin(17, Pin.OUT), rst=Pin(21, Pin.OUT)
    )
    start = time.ticks_ms()
    while True:
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, start)
        mood = (elapsed // MOOD_MS) % 9
        phase = (elapsed % MOOD_MS) / 1000
        draw_mood(mood, phase)
        display.blit(fb, 0, 0, W, H)
        time.sleep_ms(FRAME_MS)


main()
