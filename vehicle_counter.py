import argparse
import sys

import cv2
import numpy as np
from time import sleep

largura_min = 80    # Largura minima do retangulo
altura_min = 80      # Altura minima do retangulo

offset = 6            # Erro permitido entre pixel

linha_pos_pct = 0.45  # Posição da linha de contagem (fração da altura do vídeo)


def pega_centro(x, y, w, h):
    x1 = int(w / 2)
    y1 = int(h / 2)
    cx = x + x1
    cy = y + y1
    return cx, cy


def parse_args():
    parser = argparse.ArgumentParser(description="Count vehicles crossing a line in a video.")
    parser.add_argument("video", help="Path to the video file (or camera index, e.g. 0)")
    parser.add_argument("--line-pos", type=float, default=linha_pos_pct,
                         help="Counting line position as a fraction of frame height (0-1). Default: 0.45")
    parser.add_argument("--min-width", type=int, default=largura_min, help="Minimum contour width")
    parser.add_argument("--min-height", type=int, default=altura_min, help="Minimum contour height")
    parser.add_argument("--no-realtime", action="store_true",
                         help="Process as fast as possible instead of pacing to the video's FPS")
    return parser.parse_args()


def main():
    args = parse_args()

    video_source = int(args.video) if args.video.isdigit() else args.video

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        sys.exit(f"Could not open video: {args.video}")

    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_video = cap.get(cv2.CAP_PROP_FPS) or 25
    tempo = 1.0 / fps_video

    pos_linha = int(frame_h * args.line_pos)

    subtracao = cv2.bgsegm.createBackgroundSubtractorMOG()

    detec = []
    carros = 0

    while True:
        ret, frame1 = cap.read()
        if not ret:
            break

        if not args.no_realtime:
            sleep(tempo)

        grey = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(grey, (3, 3), 5)
        img_sub = subtracao.apply(blur)
        dilat = cv2.dilate(img_sub, np.ones((5, 5)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilatada = cv2.morphologyEx(dilat, cv2.MORPH_CLOSE, kernel)
        dilatada = cv2.morphologyEx(dilatada, cv2.MORPH_CLOSE, kernel)
        contorno, _ = cv2.findContours(dilatada, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        cv2.line(frame1, (25, pos_linha), (frame_w - 25, pos_linha), (255, 127, 0), 3)

        for c in contorno:
            (x, y, w, h) = cv2.boundingRect(c)
            validar_contorno = (w >= args.min_width) and (h >= args.min_height)
            if not validar_contorno:
                continue

            cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)
            centro = pega_centro(x, y, w, h)
            detec.append(centro)
            cv2.circle(frame1, centro, 4, (0, 0, 255), -1)

            for (cx, cy) in detec:
                if (pos_linha - offset) < cy < (pos_linha + offset):
                    carros += 1
                    cv2.line(frame1, (25, pos_linha), (frame_w - 25, pos_linha), (0, 127, 255), 3)
                    detec.remove((cx, cy))
                    print("car is detected : " + str(carros))

        cv2.putText(frame1, "VEHICLE COUNT : " + str(carros), (max(10, frame_w // 4), 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)
        cv2.imshow("Video Original", frame1)
        cv2.imshow("Detectar", dilatada)

        if cv2.waitKey(1) == 27:
            break

    cv2.destroyAllWindows()
    cap.release()
    print(f"Total vehicles counted: {carros}")


if __name__ == "__main__":
    main()
