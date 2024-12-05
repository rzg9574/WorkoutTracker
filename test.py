def moveUpChecker(weekCount, repRange, routine):
        minRep = int(repRange.split("-")[0])
        maxRep = int(repRange.split("-")[1])
        holdBack = False
        passFail = []
        
        for exercise in routine[1]:
            type = db.getTypeOfExercise(exercise)
            compoundPoints = 0
            nonCompoundPoints = 0
            firstSet = []
            secondSet = []
            lastSet = []
            if weekCount <= 2:
                results = db.getLastTwoPastSpecificExercise(exercise)
            else:
                results = db.getLastFourPastSpecificExercise(exercise)
                
            for session in results:
                autoFail = False
                if session['Rating'] < 5:
                   compoundPoints -= 2
                try:
                    firstSet.append(session["List_of_Workouts"][0]["Sets"][0])        
                except:
                    pass
                
                try:
                    secondSet.append(session["List_of_Workouts"][0]["Sets"][1])        
                except:
                    pass
                
                try:
                    lastSet.append(session["List_of_Workouts"][0]["Sets"][2])        
                except:
                    pass
                
                if autoFail:
                    continue
            
            if exercise == "Dead_Lifts":
                deadliftPoints = 0
                if firstSet:
                    autoFail = False
                    for set in firstSet:
                        if set["Reps"] < minRep:
                            passFail.append({exercise: "F"})
                            autoFail = True
                            break
                        if set["Reps"] >= maxRep:
                            deadliftPoints += 1
                        
                        if set["Reps"] >= minRep:
                            deadliftPoints += .5
                            
                        if set["Reps"] > minRep:
                            deadliftPoints += 1
                            

                    if autoFail:
                        continue
                    
                    
                else:
                    print("Failed")
                    passFail.append({exercise: "F"})
                    continue
                
                
                if deadliftPoints < 2:
                    print(f"Failed")
                    passFail.append({exercise: "F"})
                else:
                    print("Pass")
                    passFail.append({exercise: "P"})
                continue 
            else:          
                if firstSet:
                    autoFail = False
                    for set in firstSet:
                        if set["Reps"] < minRep:
                            passFail.append({exercise: "F"})
                            autoFail = True
                            break
                        if set["Reps"] >= maxRep:
                            compoundPoints += 1
                            
                        if set["Reps"] >= minRep:
                            compoundPoints += 2
                            
                        if set["Reps"] >= int(repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints += 1
                            
                        if set["Reps"] < int(repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints -= 2

                    if autoFail:
                        continue
                else:
                    print("Failed")
                    passFail.append({exercise: "F"})
                    continue 
                            
                if secondSet:
                    for set in secondSet:
                        if set["Reps"] < minRep:
                            compoundPoints -= 1
                        
                        if set["Reps"] >= maxRep:
                            compoundPoints += 1
                        
                        if set["Reps"] >= int(repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints += 1
                        
                        if set["Reps"] >= minRep:
                            compoundPoints += 1
                        
                        if set["Reps"] < int(repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints -= 1
                else:
                    compoundPoints -=1
                            
                if lastSet:
                    for set in lastSet:
                        if set["Reps"] < minRep:
                            compoundPoints -= .5

                        if set["Reps"] >= maxRep:
                            compoundPoints += 1
                        
                        if set["Reps"] >= int(repRangeKey[type["Type"]].split("-")[-1]):
                            nonCompoundPoints+= 1
                        
                        if set["Reps"] >= minRep:
                            compoundPoints += .5
                            
                        if set["Reps"] < int(repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints -= 1
                else:
                    compoundPoints -= 2
                    nonCompoundPoints -=2    

            
                if type["Type"] == "Full_Compound":    
                    if compoundPoints >= 3:
                        print(f"Pass")
                        passFail.append({exercise: "P"})
                    elif compoundPoints <= 1.5:
                        print("Fail +")
                        passFail.append({exercise: "F+"})
                    else:
                        print("Fail")
                        passFail.append({exercise: "F"})
                    
                else:
                    if nonCompoundPoints >= 3:
                        print(f"Pass")
                        passFail.append({exercise: "P"})
                    elif compoundPoints <= 1.5:
                        print("Fail +")
                        passFail.append({exercise: "F+"})
                    else:
                        print("Fail")
                        passFail.append({exercise: "F"})
                        
        print(passFail)
        for exercise in passFail:
            exerciseName, grade = next(iter(exercise.items()))
            type = db.getTypeOfExercise(exerciseName)
            if type["Type"] == "Full_Compound" and grade == "F":
                holdBack = True
                
            if grade == "P":
                db.setExerciseMoveUpTrue(exerciseName)
            if grade == "F+":
                db.setExerciseMoveUpFalse(exerciseName)
        
        
        if holdBack:
            return weekCount - 1
        else: 
            return weekCount
                
    