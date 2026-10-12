"""Render a synthetic Synthesia-style video from known notes (independent of app code)."""
import cv2
import numpy as np

WHITE = [0, 2, 4, 5, 7, 9, 11]
RIGHT_BGR = (80, 200, 60)   # green
LEFT_BGR = (220, 120, 40)   # blue


def layout(first_midi, n_white, width):
    ww = width / n_white
    keys, pitch = {}, first_midi
    for i in range(n_white):
        keys[pitch] = ((i + 0.5) * ww, ww - 3, False)
        if i == n_white - 1:
            break
        if (pitch + 2) % 12 in WHITE and (pitch % 12) in WHITE and (pitch % 12) not in (4, 11):
            keys[pitch + 1] = ((i + 1) * ww, ww * 0.55, True)
            pitch += 2
        else:
            pitch += 1
    return keys


def render_video(path, notes, first_midi=21, n_white=52, w=1280, h=720, fps=30, kb_h=120,
                 speed=300.0, intro_s=0.0, tail_s=1.0):
    """notes: list of (pitch, on, off, 'R'|'L'). Notes start after intro_s."""
    keys = layout(first_midi, n_white, w)
    kb_y = h - kb_h
    notes = [(p, a + intro_s, b + intro_s, hand) for p, a, b, hand in notes]
    end = max(b for _, _, b, _ in notes) + tail_s
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))
    assert vw.isOpened()
    ww = w / n_white
    for f in range(int(end * fps)):
        t = f / fps
        img = np.full((h, w, 3), 25, np.uint8)
        if t < intro_s:
            cv2.putText(img, "INTRO", (w // 3, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 3, (200, 200, 200), 6)
            vw.write(img)
            continue
        img[kb_y:] = 240
        for i in range(1, n_white):
            img[kb_y:, int(i * ww)] = 70
        for p, (xc, kw, black) in keys.items():
            if black:
                img[kb_y : kb_y + int(0.6 * kb_h), int(xc - kw / 2) : int(xc + kw / 2)] = 15
        for p, a, b, hand in notes:
            xc, kw, black = keys[p]
            col = RIGHT_BGR if hand == "R" else LEFT_BGR
            x0, x1 = int(xc - kw / 2), int(xc + kw / 2)
            bottom = min(kb_y, kb_y - (a - t) * speed)
            top = kb_y - (b - t) * speed
            if bottom > 0 and top < kb_y and bottom > top:
                img[max(0, int(top)) : int(bottom), x0:x1] = col
            if a <= t < b:
                y_end = kb_y + int((0.6 if black else 1.0) * kb_h)
                img[kb_y + 2 : y_end - 2, x0:x1] = col
        vw.write(img)
    vw.release()
