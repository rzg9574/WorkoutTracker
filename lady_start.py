from app import *

if __name__ == "__main__":

    ladyTextState = TextState()
    ladyCoach = Coach(ladyTextState, "Lady", True)
    
    listener = TextListener(ladyCoach, ladyTextState, True)    
     
    lady_thread = threading.Thread(target=ladyCoach.openLoop, daemon=True)
    listener_thread = threading.Thread(target=listener.start_listening, daemon=True)

    lady_thread.start()
    listener_thread.start()

    lady_thread.join()
    listener_thread.join()  
