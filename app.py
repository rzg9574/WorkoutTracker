from pymongo import MongoClient
from dotenv import load_dotenv 
import os
import json
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import datetime
import time

class Session:
    workouts = []
    date = None 
    rating = None
    day = None 
    
    def __init__(self, workouts, date, rating, day):
        self.workouts = workouts
        self.date = date 
        self.rating = rating
        self.day = day 
        
    def getWorkouts(self):
        return self.workouts
    
    def getDate(self):
        return self.date

    def getRating(self):
        return self.rating
    
    def getDay(self):
        return self.day
    
    def __str__(self):
        text = f"{self.day} {self.date} Rating({self.rating}):\n"
        for workout in self.workouts:
            text += str(workout)
            
        return text
    
        
        
class Set:
    weight = "" 
    reps = ""
    
    def __init__ (self, weight, reps):
        self.weight = weight 
        self.reps = reps
        
    def getWeight(self):
        return self.weight
    
    def getReps(self):
        return self.reps
    
    def getJson(self):
        return {"Weight":self.weight, "Reps":self.reps}
        
    def __str__(self):
        return f"{self.weight} X {self.reps}" 
    
    
    
class Workout:
    name = ""
    sets = []
    
    def __init__ (self, name, sets):
        self.name  = name
        self.sets = sets
        
        
    def getName(self):
        return self.name
    
    def getSets(self):
        return self.sets
    
    def getNumberOfSets(self):
        return len(self.sets)
    
    def getSetJson(self):
        listOfSets = []
        for s in self.sets:
            listOfSets.append(s.getJson())
        return listOfSets
    
    def getJson(self):
        return {"Name":self.name, "Sets":self.getSetJson()}
    
    def __str__(self):
        text = f"{self.name}({self.getNumberOfSets()} sets):\n"
        for s in self.sets:
            text += str(s) + "\n"
            
        return text
         

class DBController:
    
    db = None 
    workOutsCollection = None
    exerciseCollection = None 
    
    def __init__(self):
        load_dotenv()
        dbLogin = os.environ.get('dbLogin')
        client = MongoClient(dbLogin)
        self.db = client["WorkoutTracker"]
        self.workOutsCollection = self.db["Workouts"]
        self.exerciseCollection = self.db["Exercises"]
        print("Database Initialized")
        
    def getLastSession(self):
        response = self.workOutsCollection.find_one(sort=[("_id", -1)])
        
        workouts = []
        for workout in response["List_of_Workouts"]:
            workouts.append(Workout(workout["Name"],[Set(s["Weight"], s["Reps"]) for s in workout["Sets"]]))

        session = Session(workouts, response["Date"], response["Rating"], response["Day"])
        
        return session
    
    def getAllSessions(self):
        sessions = []
        responses = self.workOutsCollection.find(sort=[("_id", -1)]).limit(30)
        for response in responses:
            workouts = []
            for workout in response["List_of_Workouts"]:
                workouts.append(Workout(workout["Name"],[Set(s["Weight"], s["Reps"]) for s in workout["Sets"]]))

            session = Session(workouts, response["Date"], response["Rating"], response["Day"])
            sessions.append(session)
            
        return sessions
    
    def postWorkOut(self, workout):
        if type(workout) == Workout:
            self.workOutsCollection.insert_one(workout.getJson())
            
        
    def loadInExercises(self, textFile):
        with open(textFile) as exercises:
            text = exercises.readlines() 
            for line in text:
                splitLine = line.split(",") 
                
                if len(splitLine) >= 2:
                    result = self.exerciseCollection.find_one({"Name":splitLine[0]})
                    if not result:
                        self.exerciseCollection.insert_one({"Name":splitLine[0], "Type": splitLine[1].replace("\n", ""), "Move_Up_Rate": int(splitLine[2]) if len(splitLine) > 2 else 10, "Move_Up": False })
                    else:
                        print(f"{splitLine[0]} is already in the database updating it")
                        self.exerciseCollection.replace_one({"Name":splitLine[0]}, {"Name":splitLine[0], "Type": splitLine[1].replace("\n", ""), "Move_Up_Rate": int(splitLine[2]) if len(splitLine) > 2 else 10, "Move_Up": False }, True)
                    
    def getAllPastSpecificExercise(self, exercise):
        return self.workOutsCollection.find({ "List_of_Workouts.Name": exercise},{ "List_of_Workouts.$": 1 }, sort=[("_id", -1)])               
    
    def getLastTwoPastSpecificExercise(self, exercise):
        return self.workOutsCollection.find({ "List_of_Workouts.Name": exercise},{ "List_of_Workouts.$": 1, "Rating": 1}, sort=[("_id", -1)]).limit(2)
    
    def getLastFourPastSpecificExercise(self, exercise):
        return self.workOutsCollection.find({ "List_of_Workouts.Name": exercise},{ "List_of_Workouts.$": 1, "Rating": 1}, sort=[("_id", -1)]).limit(4)
    
    def getTypeOfExercise(self, exercise):
        return self.exerciseCollection.find_one({"Name": exercise})
    
    def setExerciseMoveUpTrue(self, exercise):
        return self.exerciseCollection.update_one({"Name": exercise}, { "$set": { "Move_Up": True } })
    
    def setExerciseMoveUpFalse(self, exercise):
        return self.exerciseCollection.update_one({"Name": exercise}, { "$set": { "Move_Up": False } })      
    

class Coach:
    cycle = []
    pullRepRangeCycle = []
    pushRepRangeCycle = []
    legsRepRangeCycle = []
    repRangeKey = {}
    startingPercentage = 0.82
    db = DBController()
    routine = None
    routineFile = "routine.json"
    day = "Push"
    
    
    def __init__(self):
        self.loadInRoutine()
        self.cycle = [["Pull",self.routine["Pull"]], ["Push",self.routine["Push"]], ["Legs",self.routine["Legs"]]]
        self.pullRepRangeCycle = ["2-4", "4-6", "6-8"]
        self.pushRepRangeCycle = ["2-4", "4-6", "6-8"]
        self.legsRepRangeCycle = ["2-4", "4-6", "6-8"]
        self.repRangeKey = {"Full_Compound": "USE REP RANGE CYCLE", "Semi_Compound": "6-8", "Non_Compound":"10-15", "Body_Weight": "To Failure"}
        
                
    def loadInRoutine(self):
        with open(self.routineFile, 'r') as file:
            self.routine = json.load(file)

            
    
    def logWorkout(self, name, weight, sets, reps):
        workout = Workout(name, weight, sets, reps)
        self.db.postWorkOut(workout)
        
    
    def sendText(self, msg):
        load_dotenv()
        sid = os.environ.get('SID')
        token = os.environ.get("token")
        
        client = Client(sid, token)
        message = client.messages.create(
            to = os.environ.get('myPhoneNumber'),
            from_ = os.environ.get('twilloPhoneNumber'),
            body= msg
        )
        return message.sid
        
    
    def decideToadysWorkOut(self, repRange, todaysRoutine):
        self.day = todaysRoutine[0]
        message = "Do This Today:\n"
        for workout in todaysRoutine[1]:
            message += f"{workout}:\n"
            allOldSets = []
            oldSessions = self.db.getAllPastSpecificExercise(workout)
            for session in oldSessions:
                allOldSets.append(Set(session["List_of_Workouts"][0]["Sets"][0]["Weight"], session["List_of_Workouts"][0]["Sets"][0]["Reps"]))

            typeOfExersice = self.db.getTypeOfExercise(workout)
            
            if typeOfExersice["Type"] == "Full_Compound":
                if typeOfExersice["Move_Up"]:
                    self.db.setExerciseMoveUpFalse(workout)
                    message += f"Top set of {int(allOldSets[0].getWeight()) + typeOfExersice['Move_Up_Rate']} ==> {repRange}\n"
                else:
                    message += f"Top set of {int(allOldSets[0].getWeight())} ==> {repRange}\n"
                    
            elif typeOfExersice["Type"] == "Non_Compound":
                if typeOfExersice["Move_Up"]:
                    self.db.setExerciseMoveUpFalse(workout)
                    message += f"{int(allOldSets[0].getWeight()) + typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{int(allOldSets[0].getWeight()) + typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{int(allOldSets[0].getWeight()) + typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                else:
                    message += f"{int(allOldSets[0].getWeight())} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{int(allOldSets[0].getWeight())} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{int(allOldSets[0].getWeight())} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    
            elif typeOfExersice['Type'] == "Semi_Compound" or typeOfExersice['Type'] == "Body_Weight":
                if typeOfExersice["Move_Up"]:
                    self.db.setExerciseMoveUpFalse(workout)
                    if typeOfExersice["Name"] == "Pull_Ups":
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    else:
                        message += f"{int(allOldSets[0].getWeight()) + typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{int(allOldSets[0].getWeight()) - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{int(allOldSets[0].getWeight()) - (2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                else:
                    if typeOfExersice["Name"] == "Pull_Ups":
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    else:
                        message += f"{int(allOldSets[0].getWeight())} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{int(allOldSets[0].getWeight())} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{int(allOldSets[0].getWeight()) - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
        
        self.sendText(message)
        print(message)
    
    def incomingText(self, text):
        load_dotenv()
        sets = []
        workouts = []
        session = None
        nextOne = True
        name = None
        weight = None
        reps = None
        text = text.replace(f"Message from {os.environ.get('myPhoneNumber')}:", "")
        splitText = text.split("\n")
        for t in splitText:
            if "Rating" in t:
                break
            if ":" in t:
                if name:
                    if sets:
                        workouts.append(Workout(name, sets))
                        sets = []
                index = text.find(":")
                name = text[:index]
            
            tempSplit = t.split("x")
            weight = tempSplit[0]
            reps = tempSplit[1]
            sets.append(Set(weight, reps))
            
        
        session = Session(workouts, datetime.datetime.today(), int(splitText[-1].replace("Rating:"), ""), self.day)
        print(session)
        return session
    
    
    def loadInNewWorkouts(self, file):
        self.db.loadInExercises(file)
    
    def moveUpChecker(self, weekCount, repRange, routine):
        minRep = int(repRange.split("-")[0])
        maxRep = int(repRange.split("-")[1])
        holdBack = False
        passFail = []
        
        for exercise in routine[1]:
            goodPoints = 0
            firstSet = []
            secondSet = []
            lastSet = []
            if weekCount <= 2:
                results = self.db.getLastTwoPastSpecificExercise(exercise)
            else:
                results = self.db.getLastFourPastSpecificExercise(exercise)
                
            for session in results:
                autoFail = False
                if session['Rating'] < 5:
                   goodPoints -= 2
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
                    
            if firstSet:
                autoFail = False
                for set in firstSet:
                    if set["Reps"] < minRep:
                        passFail.append({exercise: "F"})
                        autoFail = True
                        break
                    if set["Reps"] >= maxRep:
                        goodPoints += 1
                        
                    if set["Reps"] >= minRep:
                        goodPoints += 2

                if autoFail:
                    continue
            else:
                print("Failed")
                passFail.append({exercise: "F"})
                continue 
                        
            if secondSet:
                for set in secondSet:
                    if set["Reps"] < minRep:
                        goodPoints -= 1
                    
                    if set["Reps"] >= maxRep:
                        goodPoints += 1
                    
                    if set["Reps"] >= minRep:
                        goodPoints += 1
            else:
                goodPoints -=1
                        
            if lastSet:
                for set in lastSet:
                    if set["Reps"] < minRep:
                        goodPoints -= .5
               
                    if set["Reps"] >= maxRep:
                        goodPoints += 1
                    
                    if set["Reps"] >= minRep:
                        goodPoints += .5
            else:
                goodPoints -= 2    

        
           
            if goodPoints < 3:
                print(f"Failed")
                passFail.append({exercise: "F"})
            else:
                print("Pass")
                passFail.append({exercise: "P"})
            
        
        
        for exercise in passFail:
            exerciseName, grade = next(iter(exercise.items()))
            type = self.db.getTypeOfExercise(exerciseName)
            if type["Type"] == "Full_Compound" and grade == "F":
                holdBack = True
                
            if grade == "P":
                self.db.setExerciseMoveUpTrue(exerciseName)
        
        
        if holdBack:
            return weekCount - 1
        else: 
            return weekCount
                
    
    def cycleAllRepRanges(self):
        pullRepRange = self.pullRepRangeCycle.pop()
        self.pullRepRangeCycle.append(pullRepRange)
        
        pushRepRange = self.pushRepRangeCycle.pop()
        self.pushRepRangeCycle.append(pushRepRange)
        
        legsRepRange = self.legsRepRangeCycle.pop()
        self.legsRepRangeCycle.append(legsRepRange)

        return pullRepRange, pushRepRange, legsRepRange
    
    def openLoop(self):
        startHour = 5
        startMinute = 30
        weekTracker = False 
        pullWeekCount = 0
        pushWeekCount = 0
        legsWeekCount = 0
        dayTracker = False
        pullRepRange, pushRepRange, legsRepRange = self.cycleAllRepRanges()
        todaysRoutine = self.cycle.pop()
        self.cycle.append(todaysRoutine)
        while True:
            now = datetime.datetime.now()
            
            if now.weekday() == 0 and now.hour == startHour and now.minute == startMinute and not weekTracker:
                if pullWeekCount == 1:
                    pullWeekCount = self.moveUpChecker(pullWeekCount, pullRepRange, todaysRoutine)
                elif pullWeekCount == 3:
                    pullWeekCount = self.moveUpChecker(pullWeekCount, pullRepRange, todaysRoutine)
                elif pullWeekCount == 4:
                    pullWeekCount = 0
                    pullRepRange = self.pullRepRangeCycle.pop()
                    self.pullRepRangeCycle.append(pullRepRange)
                    
                
                if pushWeekCount == 1:
                    pushWeekCount = self.moveUpChecker(pushWeekCount, pushRepRange, todaysRoutine)
                elif pushWeekCount == 3:
                    pushWeekCount = self.moveUpChecker(pushWeekCount, pushRepRange, todaysRoutine)
                elif pushWeekCount == 4:
                    pushWeekCount = 0
                    pushRepRange = self.pushRepRangeCycle.pop()
                    self.pushRepRangeCycle.append(pushRepRange)
                
                
                if legsWeekCount == 1:
                    legsWeekCount = self.moveUpChecker(legsWeekCount, legsRepRange, todaysRoutine)
                elif legsWeekCount == 3:
                    legsWeekCount = self.moveUpChecker(legsWeekCount, legsRepRange, todaysRoutine)
                elif legsWeekCount == 4:
                    legsWeekCount = 0
                    legsRepRange = self.legsRepRangeCycle.pop()
                    self.legsRepRangeCycle.append(legsRepRange)
                
                pullWeekCount += 1
                pushWeekCount += 1
                legsWeekCount += 1
                weekTracker = True
                time.sleep(60)

            # Reset weekly flag on any day other than the first day of the week
            if now.weekday() != 0:
                weekTracker = False
            
            if now.hour == startHour and now.minute == startMinute and not dayTracker:
                if todaysRoutine[0] == "Push":
                    self.decideToadysWorkOut(pushRepRange, todaysRoutine)
                elif todaysRoutine[0] == "Pull":
                    self.decideToadysWorkOut(pullRepRange, todaysRoutine)
                else:
                    self.decideToadysWorkOut(legsRepRange, todaysRoutine)
                    
                todaysRoutine = self.cycle.pop()
                self.cycle.append(todaysRoutine)
                dayTracker = True
                time.sleep(60)
            
            if now.hour == 0 and now.minute == 0:
                dayTracker = False
                
            time.sleep(10)
        
        

# Coach().incomingText(
# """
# Message from +13477839604: Dead Lifts:
# 345x6
# Rows:
# 155x6
# 135x8
# 135x4
# Pull ups:
# 8
# 6
# 5
# hammer curls:
# 30x12
# 30x6
# 25x12
# machine curls:
# 65x8
# 60x8
# 50x10
# rating:8
# """)

Coach().openLoop()