import cv2
import json

VIDEO_SOURCE = "rtsp://192.168.1.110/live.sdp"   # or 0 for webcam
OUT_FILE     = "avg_bg_color.json"   # output JSON file

def mean_bgr(img):
    """Return the per-channel mean of a BGR image."""
    return cv2.mean(img)[:3]

def main():
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    ret, frame = cap.read()
    if not ret:
        print("Failed to open video.")
        return

    # Let user select the background ROI
    roi = cv2.selectROI("Select Background ROI", frame, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()
    x, y, w, h = map(int, roi)
    if w == 0 or h == 0:
        print("No ROI selected, exiting.")
        return

    # Crop and compute mean color
    bg_crop    = frame[y:y+h, x:x+w]
    b_mean, g_mean, r_mean = mean_bgr(bg_crop)

    # Save to JSON
    data = {"b": b_mean, "g": g_mean, "r": r_mean}
    with open(OUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved average background color to {OUT_FILE}")

if __name__ == "__main__":
    main()
