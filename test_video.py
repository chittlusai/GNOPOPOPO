import cv2
import time
import os
from ffpyplayer.player import MediaPlayer

def play_video():
    video_path = r"C:\Users\RAM\Downloads\gemini_generated_video_f2301781.mp4"
    if not os.path.exists(video_path):
        print(f"File not found: {video_path}")
        return

    cap = cv2.VideoCapture(video_path)
    player = MediaPlayer(video_path)

    start_time = time.time()
    
    cv2.namedWindow('Video Intro', cv2.WINDOW_NORMAL)
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        audio_frame, val = player.get_frame()
        if val == 'eof':
            break
            
        elapsed = time.time() - start_time
        
        if elapsed >= 8.0:
            break
            
        if elapsed > 6.0:
            fade = max(0, 1.0 - (elapsed - 6.0) / 2.0)
            frame = cv2.convertScaleAbs(frame, alpha=fade, beta=0)
            player.set_volume(fade)
            
        cv2.imshow('Video Intro', frame)
        
        if cv2.waitKey(28) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    player.close_player()

if __name__ == "__main__":
    play_video()
