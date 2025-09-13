import cv2
import numpy as np
import time

# --- Configuration ---
VIDEO_SOURCE        = "rtsp://192.168.1.110/live.sdp"  # or 0 for webcam
DISPLAY_WIDTH       = 800                  # width of display window
NUM_ROWS            = 5                    # number of horizontal lines to sample
COLOR_THRESH        = 220.0                 # color distance threshold
TARGET_FPS          = 20                   # display/update rate in Hz
TOP_MARGIN_RATIO    = 0.2                  # top margin (fraction of height)
BOTTOM_MARGIN_RATIO = 0.6                  # bottom margin (fraction of height)
WIDTH_THRESHOLD     = 5.0                  # allowed deviation from initial width

def estimate_bg_from_row(frame):
    """
    Take the central horizontal row of pixels, cluster its colors into two groups (bg vs shell)
    by k-means in 1D on intensity, and return the mean BGR of the background cluster.
    """
    h, w = frame.shape[:2]
    y = h // 2
    row = frame[y, :, :].reshape(-1, 3).astype(np.float32)
    # convert to intensity for clustering
    intensities = cv2.cvtColor(row.reshape(1, -1, 3), cv2.COLOR_BGR2GRAY).reshape(-1,1)
    # k-means into 2 clusters
    _, labels, centers = cv2.kmeans(intensities, 2, None,
                                    (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                                    3, cv2.KMEANS_PP_CENTERS)
    # Determine which cluster is background: the one with the larger count
    counts = np.bincount(labels.flatten())
    bg_label = np.argmax(counts)
    # mask of background pixels in the row
    bg_mask = (labels.flatten() == bg_label)
    # compute mean BGR of those pixels
    bg_pixels = row[bg_mask]
    return bg_pixels.mean(axis=0)

def main():
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    ret, first = cap.read()
    if not ret:
        print("Failed to open video.")
        return

    h, w = first.shape[:2]
    top_m    = int(h * TOP_MARGIN_RATIO)
    bottom_m = int(h * BOTTOM_MARGIN_RATIO)
    sample_ys = np.linspace(top_m, h - bottom_m - 1, NUM_ROWS, dtype=int)
    kernel   = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
    thresh2  = COLOR_THRESH**2

    # estimate background color from central row of first frame
    bg_mean = estimate_bg_from_row(first).astype(np.float32)

    # compute initial mask & width
    diff2 = np.sum((first.astype(np.float32) - bg_mean)**2, axis=2)
    mask0 = diff2 > thresh2
    mask0 = cv2.morphologyEx(mask0.astype(np.uint8)*255, cv2.MORPH_OPEN,  kernel)
    mask0 = cv2.morphologyEx(mask0,                         cv2.MORPH_CLOSE, kernel)
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
    last_time    = time.time()
    avg_width_1s = initial_width

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # you may re-estimate bg_mean here if lighting changes:
        # bg_mean = estimate_bg_from_row(frame)

        # build & clean mask
        diff2     = np.sum((frame.astype(np.float32) - bg_mean)**2, axis=2)
        mask_full = diff2 > thresh2
        m         = cv2.morphologyEx(mask_full.astype(np.uint8)*255, cv2.MORPH_OPEN,  kernel)
        m         = cv2.morphologyEx(m,                             cv2.MORPH_CLOSE, kernel)
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
            vis[y, row]  = (0, 255, 0)
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
            status = f"OK Δ={dev:.1f}px"
            col    = (0,255,0)
        else:
            status = f"ALERT Δ={dev:.1f}px"
            col    = (0,0,255)

        cv2.putText(vis, f"Init: {initial_width:.1f}px", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        cv2.putText(vis, f"Avg1s: {avg_width_1s:.1f}px", (10,60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)
        cv2.putText(vis, status, (10,90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

        show = cv2.resize(vis, (DISPLAY_WIDTH, int(h * DISPLAY_WIDTH / w)))
        cv2.imshow("Shell Width Sampling", show)
        if cv2.waitKey(int(1000 / TARGET_FPS)) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
