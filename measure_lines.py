import cv2
import numpy as np
import time
import json

# --- Configuration ---
VIDEO_SOURCE      = 1
DISPLAY_WIDTH     = 800                               
NUM_ROWS          = 5                                 # lines num
COLOR_THRESH      = 220.0                             # color threshold to become shell
TARGET_FPS        = 20                                
TOP_MARGIN_RATIO  = 0.4                               # lines top margin
BOTTOM_MARGIN_RATIO = 0.4                             # lines bottom margin
BG_COLOR_FILE     = "avg_bg_color.json"               # JSON with avg color value
WIDTH_THRESHOLD   = 5.0                               

def load_bg_mean(filename):
    """Загрузить усредненный цвет фона из JSON."""
    with open(filename, "r") as f:
        d = json.load(f)
    return np.array([d["b"], d["g"], d["r"]], dtype=np.float32)

def main():
    bg_mean = load_bg_mean(BG_COLOR_FILE)
    thresh2 = COLOR_THRESH**2

    cap = cv2.VideoCapture(VIDEO_SOURCE)

    ret, first = cap.read()
    if not ret:
        print("Ошибка открытия видео.")
        return

    h, w = first.shape[:2]
    top_margin = int(h * TOP_MARGIN_RATIO)
    bottom_margin = int(h * BOTTOM_MARGIN_RATIO)
    sample_ys = np.linspace(top_margin, h - bottom_margin - 1, NUM_ROWS, dtype=int)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    # --- first frame ---
    diff2 = np.sum((first.astype(np.float32) - bg_mean)**2, axis=2)
    mask0 = diff2 > thresh2
    mask0 = cv2.morphologyEx(mask0.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel)
    mask0 = cv2.morphologyEx(mask0, cv2.MORPH_CLOSE, kernel)
    mask0 = mask0.astype(bool)

    initial_widths = []
    for y in sample_ys:
        row = mask0[y, :]
        if row.any():
            xs = np.where(row)[0]
            row[xs[0]:xs[-1]+1] = True
            initial_widths.append(xs[-1] - xs[0])
        else:
            initial_widths.append(0)
    initial_width = float(np.mean(initial_widths))

    width_buffer = []
    last_time = time.time()
    avg_width_1s = initial_width

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        diff2 = np.sum((frame.astype(np.float32) - bg_mean)**2, axis=2)
        mask_full = diff2 > thresh2
        m = cv2.morphologyEx(mask_full.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
        mask_full = m.astype(bool)

        vis = frame.copy()
        per_widths = []

        for y in sample_ys:
            row = mask_full[y, :].copy()
            if row.any():
                xs = np.where(row)[0]
                row[xs[0]:xs[-1]+1] = True
                width = xs[-1] - xs[0]
            else:
                width = 0
            per_widths.append(width)
            vis[y, row] = (0, 255, 0)
            vis[y, ~row] = (255, 255, 255)

        frame_avg = float(np.mean(per_widths))
        width_buffer.append(frame_avg)

        now = time.time()
        if now - last_time >= 1.0:
            avg_width_1s = float(np.mean(width_buffer)) if width_buffer else 0.0
            width_buffer.clear()
            last_time = now

        dev = abs(avg_width_1s - initial_width)
        if dev <= WIDTH_THRESHOLD:
            status = f"OK {dev:.1f}px"
            col = (0, 255, 0)
        else:
            status = f"ALERT {dev:.1f}px"
            col = (0, 0, 255)

        # Text shadow
        cv2.putText(vis, f"Init: {initial_width:.1f}px", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)
        cv2.putText(vis, f"Avg W: {avg_width_1s:.1f}px", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)
        cv2.putText(vis, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)

        # Overlay text
        cv2.putText(vis, f"Init: {initial_width:.1f}px", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(vis, f"Avg W: {avg_width_1s:.1f}px", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(vis, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, col, 2)

        scale = DISPLAY_WIDTH / w
        show = cv2.resize(vis, (DISPLAY_WIDTH, int(h * scale)))

        cv2.imshow("Shell Width Sampling", show)
        if cv2.waitKey(int(1000 / TARGET_FPS)) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
