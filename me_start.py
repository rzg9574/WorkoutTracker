from app import *

if __name__ == "__main__":
    myTextState = TextState() 
    myCoach = Coach(myTextState, "PPL", False)
    
    listener = TextListener(myCoach, myTextState, False)    
     
    coach_thread = threading.Thread(target=myCoach.openLoop, daemon=True)
    listener_thread = threading.Thread(target=listener.start_listening, daemon=True)

    coach_thread.start()
    listener_thread.start()

    coach_thread.join()
    listener_thread.join()  
