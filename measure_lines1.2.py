import cv2
import numpy as np
import time
import json

# --- Configuration ---
VIDEO_SOURCE        = "rtsp://192.168.1.110/live.sdp"  # or 0 for webcam
DISPLAY_WIDTH       = 800                              # width of display window
NUM_ROWS            = 5                                # number of horizontal lines to sample
COLOR_THRESH        = 50.0                            # color threshold to become shell
TARGET_FPS          = 20                               # display/update rate in Hz
TOP_MARGIN_RATIO    = 0.25                              # lines top margin (fraction of height)
BOTTOM_MARGIN_RATIO = 0.65                              # lines bottom margin (fraction of height)
BG_COLOR_FILE       = "avg_bg_color.json"              # JSON with avg color value
WIDTH_THRESHOLD     = 5.0                              # allowed deviation from initial width

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

    # --- first frame for initial width ---
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
            initial_widths.append(xs[-1] - xs[0])
        else:
            initial_widths.append(0)
    initial_width = float(np.mean(initial_widths))

    # Buffers for rolling averages
    width_buffer   = []
    x1_buffer      = []
    x2_buffer      = []
    last_time      = time.time()
    avg_width_1s   = initial_width
    avg_x1_1s      = 0.0
    avg_x2_1s      = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # build and clean mask
        diff2     = np.sum((frame.astype(np.float32) - bg_mean)**2, axis=2)
        mask_full = diff2 > thresh2
        m         = cv2.morphologyEx(mask_full.astype(np.uint8)*255, cv2.MORPH_OPEN, kernel)
        m         = cv2.morphologyEx(m,                            cv2.MORPH_CLOSE, kernel)
        mask_full = m.astype(bool)

        vis = frame.copy()
        per_widths = []
        per_x1     = []
        per_x2     = []

        # Measure width and X1, X2 on each sample row
        for y in sample_ys:
            row = mask_full[y, :]
            if row.any():
                xs = np.where(row)[0]
                x1, x2 = xs[0], xs[-1]
                per_x1.append(x1)
                per_x2.append(x2)
                per_widths.append(x2 - x1)
                # fill for visualization
                row[x1:x2+1] = True
            else:
                per_x1.append(0)
                per_x2.append(0)
                per_widths.append(0)
            vis[y, row]  = (0, 255, 0)
            vis[y, ~row] = (255, 255, 255)

        # Update buffers
        frame_avg = float(np.mean(per_widths))
        width_buffer.append(frame_avg)
        x1_buffer.append(np.mean(per_x1))
        x2_buffer.append(np.mean(per_x2))

        # Once per second compute rolling averages
        now = time.time()
        if now - last_time >= 1.0:
            avg_width_1s = float(np.mean(width_buffer)) if width_buffer else 0.0
            avg_x1_1s    = float(np.mean(x1_buffer))     if x1_buffer    else 0.0
            avg_x2_1s    = float(np.mean(x2_buffer))     if x2_buffer    else 0.0
            width_buffer.clear()
            x1_buffer.clear()
            x2_buffer.clear()
            last_time = now

        # Check deviation
        dev = abs(avg_width_1s - initial_width)
        if dev <= WIDTH_THRESHOLD:
            status = f"OK {dev:.1f}px"
            col    = (0, 255, 0)
        else:
            status = f"ALERT {dev:.1f}px"
            col    = (0, 0, 255)

        # Text shadow
        cv2.putText(vis, f"Init: {initial_width:.1f}px", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)
        cv2.putText(vis, f"Avg W: {avg_width_1s:.1f}px", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)
        cv2.putText(vis, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)
        cv2.putText(vis, f"Avg X1: {avg_x1_1s:.1f}", (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)
        cv2.putText(vis, f"Avg X2: {avg_x2_1s:.1f}", (10, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5)

        # Overlay text
        cv2.putText(vis, f"Init: {initial_width:.1f}px", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(vis, f"Avg W: {avg_width_1s:.1f}px", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(vis, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, col, 2)
        cv2.putText(vis, f"Avg X1: {avg_x1_1s:.1f}", (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(vis, f"Avg X2: {avg_x2_1s:.1f}", (10, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

        # Resize and show
        show = cv2.resize(vis, (DISPLAY_WIDTH, int(h * DISPLAY_WIDTH / w)))
        cv2.imshow("Shell Width Sampling", show)
        if cv2.waitKey(int(1000 / TARGET_FPS)) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
