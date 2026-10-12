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
                 speed=300.0, intro_s=0.0, tail_s=1.0, glow=False, seam_px=0, labels=False, dim_black=False, dark_seam=False):
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
        for p, a, b, hand in notes:  # lit white keys go under the black keys
            xc, kw, black = keys[p]
            if not black and a <= t < b:
                col = RIGHT_BGR if hand == "R" else LEFT_BGR
                img[kb_y + 2 : h - 2, int(xc - kw / 2) : int(xc + kw / 2)] = col
        for p, (xc, kw, black) in keys.items():
            if black:  # idle black keys have a faint blue sheen like real videos
                img[kb_y : kb_y + int(0.6 * kb_h), int(xc - kw / 2) : int(xc + kw / 2)] = (60, 30, 25)
        for p, a, b, hand in notes:
            xc, kw, black = keys[p]
            col = RIGHT_BGR if hand == "R" else LEFT_BGR
            if black and dim_black:  # lit black keys can be dim in real videos (V ~ 130-150)
                col = tuple(int(c * 0.62) for c in col)
            x0, x1 = int(xc - kw / 2), int(xc + kw / 2)
            bottom = min(kb_y, kb_y - (a - t) * speed) - seam_px / 2
            top = kb_y - (b - t) * speed + seam_px / 2
            if bottom > 0 and top < kb_y and bottom > top:
                img[max(0, int(top)) : int(bottom), x0:x1] = col
                if dark_seam and bottom - top > 8:  # low-res style: a thin dark line, still bar-colored
                    img[max(0, int(bottom) - 2) : int(bottom), x0:x1] = tuple(int(c * 0.5) for c in col)
            if labels and bottom - top > 40:  # a white note-name blob mid-bar; wide on black keys
                cy = int((top + bottom) / 2)
                lx0, lx1 = (x0, x1) if black else (int(xc - kw * 0.3), int(xc + kw * 0.3))
                if 0 <= cy - 5 and cy + 5 < kb_y:
                    img[cy - 5 : cy + 5, lx0:lx1] = (165, 165, 165)  # light gray like the real labels
            if black and a <= t < b:
                img[kb_y : kb_y + int(0.6 * kb_h), x0:x1] = col
        if glow:  # sparks and glow where the notes land, like real videos
            rng = np.random.default_rng(f)
            for _ in range(60):
                x, y = rng.integers(0, w), rng.integers(kb_y - 40, kb_y)
                cv2.circle(img, (int(x), int(y)), int(rng.integers(1, 4)),
                           RIGHT_BGR if rng.random() < 0.5 else LEFT_BGR, -1)
        vw.write(img)
    vw.release()
