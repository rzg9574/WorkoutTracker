from pymongo import MongoClient
from dotenv import load_dotenv 
import os
import json
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import datetime
import time
import threading
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from enum import Enum
import logging

class MoveUp(Enum):
    UP = "U"
    DOWN = "D"
    STAY = "S"

class Compound(Enum):
    NON_COMPOUND = "N"
    COMPOUND = "C"
    SEMI_COMPOUND = "S"
    CARDIO = "CO"

class Session:
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
    
    def getJson(self):
        return {"Date":self.date, "List_of_Workouts":[w.getJson() for w in self.workouts], "Rating": self.rating, "Day":self.day}
    
    def __str__(self):
        text = f"{self.day} {self.date} Rating({self.rating}):\n"
        for workout in self.workouts:
            text += str(workout)
            
        return text
    
        
        
class Set:
    def __init__ (self, weight, reps):
        self.weight = weight 
        self.reps = reps
        
    def getWeight(self):
        return int(self.weight)
    
    def getReps(self):
        return int(self.reps)
    
    def getJson(self):
        return {"Weight":int(self.weight), "Reps":int(self.reps)}
        
    def __str__(self):
        return f"{self.weight} X {self.reps}" 
    
    
    
class Workout:
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
    
    def __init__(self, LADY = False):
        load_dotenv()
        dbLogin = os.environ.get('dbLogin')
        client = MongoClient(dbLogin)
        self.db = client["WorkoutTracker"]
        if LADY:
            self.workOutsCollection = self.db["Lady_Workouts"]
            self.exerciseCollection = self.db["Lady_Exercises"]
        else:
            self.workOutsCollection = self.db["Workouts"]
            self.exerciseCollection = self.db["Exercises"]
        print("Database Initialized")
        
    def getLastSession(self):
        response = self.workOutsCollection.find_one(sort=[("_id", -1)])
        
        workouts = []
        for workout in response["List_of_Workouts"]:
            workouts.append(Workout(workout["Name"],[Set(s['Weight'], s["Reps"]) for s in workout["Sets"]]))

        session = Session(workouts, response["Date"], response["Rating"], response["Day"])
        
        return session
    
    def getAllSessions(self):
        sessions = []
        responses = self.workOutsCollection.find(sort=[("_id", -1)]).limit(30)
        for response in responses:
            workouts = []
            for workout in response["List_of_Workouts"]:
                workouts.append(Workout(workout["Name"],[Set(s['Weight'], s["Reps"]) for s in workout["Sets"]]))

            session = Session(workouts, response["Date"], response["Rating"], response["Day"])
            sessions.append(session)
            
        return sessions
    
    def postWorkOut(self, workout):
        if type(workout) == Session:
            self.workOutsCollection.insert_one(workout.getJson())
            
    
    
    def postNewWorkOut(self, name, type, moveUp, weight):
        moveUp = int(moveUp)
        result = self.exerciseCollection.find_one({"Name":name})
        if not result:
            self.exerciseCollection.insert_one({"Name":name, "Type": type, "Move_Up_Rate": moveUp, "Move_Up": MoveUp.STAY.value, "Weight":int(weight)})
        else:
            logging.warning(f"{name} is already in the database updating it")
            self.exerciseCollection.replace_one({"Name":name}, {"Name":name, "Type": type, "Move_Up_Rate": moveUp, "Move_Up": MoveUp.STAY.value, "Weight":int(weight)}, True)
        
    def loadInExercises(self, textFile):
        with open(textFile) as exercises:
            text = exercises.readlines() 
            for line in text: 
                splitLine = line.split(",") 
                
                if len(splitLine) >= 2:
                    result = self.exerciseCollection.find_one({"Name":splitLine[0]})
                    if not result:
                        self.exerciseCollection.insert_one({"Name":splitLine[0], "Type": splitLine[1].replace("\n", ""), "Move_Up_Rate": int(splitLine[2]) if len(splitLine) > 2 else 10, "Move_Up": MoveUp.STAY.value, "Weight":int(splitLine[3])})
                    else:
                        logging.warning(f"{splitLine[0]} is already in the database updating it")
                        self.exerciseCollection.replace_one({"Name":splitLine[0]}, {"Name":splitLine[0], "Type": splitLine[1].replace("\n", ""), "Move_Up_Rate": int(splitLine[2]) if len(splitLine) > 2 else 10, "Move_Up": MoveUp.STAY.value, "Weight":int(splitLine[3]) }, True)
                    
    def getAllPastSpecificExercise(self, exercise):
        return self.workOutsCollection.find({ "List_of_Workouts.Name": exercise},{ "List_of_Workouts.$": 1 }, sort=[("_id", -1)])               
    
    def getLastTwoPastSpecificExercise(self, exercise):
        return self.workOutsCollection.find({ "List_of_Workouts.Name": exercise},{ "List_of_Workouts.$": 1, "Rating": 1}, sort=[("_id", -1)]).limit(2)
    
    def getLastFourPastSpecificExercise(self, exercise):
        return self.workOutsCollection.find({ "List_of_Workouts.Name": exercise},{ "List_of_Workouts.$": 1, "Rating": 1}, sort=[("_id", -1)]).limit(4)
    
    def getTypeOfExercise(self, exercise):
        return self.exerciseCollection.find_one({"Name": exercise})
    
    def setExerciseMoveUpTrue(self, exercise):
        return self.exerciseCollection.update_one({"Name": exercise}, { "$set": { "Move_Up": MoveUp.UP.value } })
    
    def setExerciseMoveUpFalse(self, exercise):
        return self.exerciseCollection.update_one({"Name": exercise}, { "$set": { "Move_Up": MoveUp.DOWN.value } })      
    
    def setExerciseMoveUpNeural(self, exercise):
        return self.exerciseCollection.update_one({"Name": exercise}, { "$set": { "Move_Up": MoveUp.STAY.value } })
    
    def setExerciseWeight(self, exercise, newWeight):
        return self.exerciseCollection.update_one({"Name": exercise}, { "$set": { "Weight": int(newWeight) } })
    
class Coach:
    routineFile = "routine.json"
    
    def __init__(self, textState, routineType, LADY=False):
        self.repRangeCycle = {}
        self.cycle = [] 
        self.LADY = LADY
        self.routineType = routineType
        self.db = DBController(self.LADY)
        self.loadInRoutine()
        for i in range(1, self.routine[routineType]["Unique_Days"]["Number_of_Days"] + 1):
            day = self.routine[routineType]["Unique_Days"][f"day{i}"]
            self.cycle.append([day, self.routine[routineType]["Routine"][day]])
        
        self.numberOfSeparateWeeksToTrack = len(self.cycle)
        self.weekCount = {}
        for cycle in self.cycle:
            self.weekCount[cycle[0]] = self.routine[routineType]["Week_Offset"][cycle[0]]
            self.repRangeCycle[cycle[0]] = self.routine["Periodization_Cycle"]
        
        self.repRangeKey = {"Full_Compound": "4-8", "Semi_Compound": "6-8", "Non_Compound":"10-15", "Body_Weight": "7-12", "Cardio":"30-60"}
        self.todaysRoutine = self.cycle[0]
        self.textState = textState
        
        self.startingPercentage = 0.82
                
    def loadInRoutine(self):
        with open(self.routineFile, 'r') as file:
            self.routine = json.load(file)

    def changeExerciseInRoutine(self, day, old, new):
        moveUp = 10
        type = "Non_Compound"
        routine = None
        weight = 0
        
        if "(" in new and ")" in new:
            split = new.split("(")
            new = split[0]
            split = split[1].replace(")", "").split(",")
            if split[0] == Compound.COMPOUND.value:
                type = "Full_Compound"
            elif split[0] == Compound.SEMI_COMPOUND.value:
                type = "Semi_Compound"
            elif split[0] == Compound.NON_COMPOUND.value:
                type = "Non_Compound"
            elif split[0] == Compound.CARDIO.value:
                type = "Non_Compound"
            
            if len(split) > 2:
                moveUp = split[1]
                weight = split[2]
            else:
                logging.warning("Not the right format you need to tell me the move up rate and the weight your currently doing")
                return
        else:
            logging.warning("Not the right format for adding new exersie Use ()")
            return
        
        self.db.postNewWorkOut(new, type, moveUp, weight)  
        
        with open(self.routineFile, 'r') as file:
            routine = json.load(file)
        
        for i in range(len(routine[self.routineType]["Routine"][day])):
            if routine[day][i] == old:
                routine[day][i] = new
        
        with open(self.routineFile, 'w') as file:
            json.dump(routine, file)
        
        self.loadInRoutine()
        
        for i in range(3):
            temp = self.cycle.pop(0)
            self.cycle.append([temp[0], self.routine[temp[0]]])  
            
    def logWorkout(self, name, weight, sets, reps):
        workout = Workout(name, weight, sets, reps)
        self.db.postWorkOut(workout)
    
    
    def sendText(self, msg):
        load_dotenv()
        sid = os.environ.get('SID')
        token = os.environ.get("token")
        
        client = Client(sid, token)
        if self.LADY:
            message = client.messages.create(
                to = os.environ.get('ladyPhoneNumber'),
                from_ = os.environ.get('twilloPhoneNumber'),
                body= msg
            )
        else:
            message = client.messages.create(
                to = os.environ.get('myPhoneNumber'),
                from_ = os.environ.get('twilloPhoneNumber'),
                body= msg
            )
        return message.sid
        
    
    def getTodaysWorkOutMassage(self, repRange, todaysRoutine): 
        message = "Do This Today:\n"
        for workout in todaysRoutine[1]:
            message += f"{workout}:\n"
            typeOfExersice = self.db.getTypeOfExercise(workout)
            
            if typeOfExersice["Type"] == "Full_Compound":
                message += f"Top set of {typeOfExersice['Weight']} ==> {repRange}\n"
                    
            elif typeOfExersice["Type"] == "Non_Compound":
                message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                message += f"{typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                message += f"{typeOfExersice['Weight'] - (2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    
            elif typeOfExersice['Type'] == "Semi_Compound" or typeOfExersice['Type'] == "Body_Weight":
                if typeOfExersice["Move_Up"] == MoveUp.UP.value:
                    if typeOfExersice["Name"] == "Pull_Ups":
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    else:
                        message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - (2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - (3*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                elif typeOfExersice["Move_Up"] == MoveUp.DOWN.value:
                    if typeOfExersice["Name"] == "Pull_Ups":
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    else:
                        message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                else:
                    if typeOfExersice["Name"] == "Pull_Ups":
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    else:
                        message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
            elif typeOfExersice["Type"] == "Cardio":
                message += f"{typeOfExersice['Weight']} Minutes\n"
            
        self.sendText(message)
        print(f" sent you a text:{message}")
        
    def decideToadysWorkOut(self, repRange, todaysRoutine):
        message = "Do This Today:\n"
        for workout in todaysRoutine[1]:
            message += f"{workout}:\n"
            typeOfExersice = self.db.getTypeOfExercise(workout)
            
            if typeOfExersice["Type"] == "Full_Compound":
                
                if typeOfExersice["Move_Up"] == MoveUp.UP.value:
                    message += f"Top set of {typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate']} ==> {repRange}\n"
                    self.db.setExerciseWeight(typeOfExersice["Name"], typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate'])
                elif typeOfExersice["Move_Up"] == MoveUp.DOWN.value:
                    message += f"Top set of {typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {repRange}\n"
                    self.db.setExerciseWeight(typeOfExersice["Name"], typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate'])
                else:
                    message += f"Top set of {typeOfExersice['Weight']} ==> {repRange}\n"
                    
            elif typeOfExersice["Type"] == "Non_Compound":
                if typeOfExersice["Move_Up"] == MoveUp.UP.value:
                    message += f"{typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{typeOfExersice['Weight'] - (2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    self.db.setExerciseWeight(typeOfExersice["Name"], typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate'])
                elif typeOfExersice["Move_Up"] == MoveUp.DOWN.value:
                    message += f"{typeOfExersice['Weight']-typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{typeOfExersice['Weight']-(2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{typeOfExersice['Weight']-(2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    self.db.setExerciseWeight(typeOfExersice["Name"], typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate'])
                else:
                    message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    message += f"{typeOfExersice['Weight'] - (2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    
            elif typeOfExersice['Type'] == "Semi_Compound" or typeOfExersice['Type'] == "Body_Weight":
                if typeOfExersice["Move_Up"] == MoveUp.UP.value:
                    if typeOfExersice["Name"] == "Pull_Ups":
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    else:
                        message += f"{typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - (2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    self.db.setExerciseWeight(typeOfExersice["Name"], typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate'])
                elif typeOfExersice["Move_Up"] == MoveUp.DOWN.value:
                    if typeOfExersice["Name"] == "Pull_Ups":
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    else:
                        message += f"{typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - (2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - (2*typeOfExersice['Move_Up_Rate'])} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    self.db.setExerciseWeight(typeOfExersice["Name"], typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate'])
                else:
                    if typeOfExersice["Name"] == "Pull_Ups":
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"0 ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                    else:
                        message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
                        message += f"{typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate']} ==> {self.repRangeKey[typeOfExersice['Type']]}\n"
            
            elif typeOfExersice["Type"] == "Cardio":
                if typeOfExersice["Move_Up"] == MoveUp.UP.value:
                    message += f"{typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate']} Minutes\n"
                    self.db.setExerciseWeight(typeOfExersice["Name"], typeOfExersice['Weight'] + typeOfExersice['Move_Up_Rate'])
                elif typeOfExersice["Move_Up"] == MoveUp.DOWN.value:
                    message += f"{typeOfExersice['Weight']-typeOfExersice['Move_Up_Rate']} Minutes\n"
                    self.db.setExerciseWeight(typeOfExersice["Name"], typeOfExersice['Weight'] - typeOfExersice['Move_Up_Rate'])
                else:
                    message += f"{typeOfExersice['Weight']} Minutes\n"
                    
        self.sendText(message)
        print(f" sent you a text:{message}")
    
    def incomingText(self, text):
        load_dotenv()
        sets = []
        workouts = []
        workoutPlan = self.cycle[-1]
        print(f" workout plan you were suppose follow {workoutPlan[1]}")
        session = None
        nextOne = True
        name = None
        rating = -1
        weight = None
        reps = None
        if self.LADY:
            text = text.replace(f"Message from {os.environ.get('ladyPhoneNumber')}:", "")
        else:
            text = text.replace(f"Message from {os.environ.get('myPhoneNumber')}:", "")
        splitText = text.split("\n")
        i = 0
        
        try:
            for t in splitText:
                if t:
                    if "rating" in t.lower():
                        rating = t.lower().replace("rating:", "")
                        break
                    
                    if "skip" in t.lower():
                        if name:
                            if "*" in name[0]:
                                self.changeExerciseInRoutine(workoutPlan[0], workoutPlan[-1][i], name.replace("*", ""))
                                workoutPlan = self.cycle[-1]
                                
                            if sets:
                                name = process.extractOne(name , workoutPlan[1], scorer=fuzz.ratio)
                                if name and name[1] > 60:
                                    matched_name = name[0]
                                    workouts.append(Workout(matched_name, sets))
                                else:
                                    workouts.append(Workout("N/A", sets))
                                sets = []
                                
                        continue
            
                    if ":" in t or ";" in t:
                        if name:
                            if "*" in name[0]:
                                self.changeExerciseInRoutine(workoutPlan[0], workoutPlan[-1][i], name.replace("*", ""))
                                workoutPlan = self.cycle[-1]
                                
                            if sets:
                                name = process.extractOne(name , workoutPlan[1], scorer=fuzz.ratio)
                                if name and name[1] > 60:
                                    matched_name = name[0]
                                    workouts.append(Workout(matched_name, sets))
                                else:
                                    workouts.append(Workout("N/A", sets))
                                sets = []
                
                        if ":" in t:
                            index = t.find(":")
                        else:
                            index = t.find(";")
                        if index != -1:
                            name = t[:index]
                    else:
                        if "x" in t:
                            tempSplit = t.split("x")
                        elif "-" in t:
                            tempSplit = t.split("-")
                        elif "/" in t:
                            tempSplit = t.split("/")
                        else:
                            tempSplit = t.split(" ")
                            
                        if tempSplit and len(tempSplit) > 1:
                            weight = tempSplit[0]
                            reps = tempSplit[1]
                            sets.append(Set(weight, reps))
                    
            
            if name:
                if "*" in name[0]:
                    self.changeExerciseInRoutine(workoutPlan[0], workoutPlan[-1][i], name.replace("*", ""))
                    workoutPlan = self.cycle[-1]
                if sets:
                    name = process.extractOne(name , workoutPlan[1], scorer=fuzz.ratio)
                    if name and name[1] > 60:
                        matched_name = name[0]
                        workouts.append(Workout(matched_name, sets))
                    else:
                        workouts.append(Workout("N/A", sets))
                    sets = []
                
            session = Session(workouts, datetime.datetime.today(), int(rating), workoutPlan[0])
            
            self.db.postWorkOut(session)
            print(f" Processed session: {session}")
            return session
        except Exception as e:
            print(f" Failed Proccessing Text Message error: {e}")
            self.textState.resetTextState()
    
    
    def loadInNewWorkouts(self, file):
        self.db.loadInExercises(file)
    
    def moveUpChecker(self, weekCount, repRange, routine):
        minRep = int(repRange[0].split("-")[0])
        maxRep = int(repRange[0].split("-")[1])
        holdBack = False
        passFail = []
        
        for exercise in routine:
            type = self.db.getTypeOfExercise(exercise)
            compoundPoints = 0
            nonCompoundPoints = 0
            firstSet = []
            secondSet = []
            lastSet = []
                        
            results = self.db.getLastTwoPastSpecificExercise(exercise)
    
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
                            passFail.append({exercise: ["F", set]})
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
                    passFail.append({exercise: "F"})
                    continue
                
                
                if deadliftPoints < 2:
                    passFail.append({exercise: "F"})
                else:
                    passFail.append({exercise: "P"})
                continue 
            else:          
                if firstSet:
                    autoFail = False
                    for set in firstSet: 
                        if set["Reps"] <= minRep - 2:
                            passFail.append({exercise: ["F", set]})
                            autoFail = True
                            break
                        if set["Reps"] == minRep - 1:
                            compoundPoints -= 1
                            
                        if int(set['Weight']) >= int(type['Weight']):
                            compoundPoints += 0.5
                            nonCompoundPoints += 0.5
                        
                        if int(set['Weight']) < int(type['Weight']):
                            compoundPoints -= 1
                            nonCompoundPoints -= 1
                            
                        if set["Reps"] >= maxRep:
                            compoundPoints += 1
                            
                        if set["Reps"] >= minRep:
                            compoundPoints += 2
                            
                        if set["Reps"] >= int(self.repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints += 1
                            
                        if set["Reps"] < int(self.repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints -= 2

                    if autoFail:
                        continue
                else:
                    passFail.append({exercise: "F"})
                    continue 
                            
                if secondSet:
                    for set in secondSet:
                        if set["Reps"] < minRep:
                            compoundPoints -= 1
                        
                        if int(set['Weight']) >= int(type['Weight']) and set["Reps"] >= int(self.repRangeKey[type["Type"]].split("-")[0]):
                            compoundPoints += 0.5
                            nonCompoundPoints += 0.5
                        
                        if int(set['Weight']) < int(type['Weight']) - 20:
                            nonCompoundPoints -= 1
                        
                        if set["Reps"] >= maxRep:
                            compoundPoints += 1
                        
                        if set["Reps"] >= int(self.repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints += 1
                        
                        if set["Reps"] >= minRep:
                            compoundPoints += 1
                        
                        if set["Reps"] < int(self.repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints -= 1
                else:
                    compoundPoints -=1
                            
                if lastSet:
                    for set in lastSet:
                        if set["Reps"] < minRep:
                            compoundPoints -= .5
                        
                        if int(set['Weight']) >= int(type['Weight']) and set["Reps"] >= int(self.repRangeKey[type["Type"]].split("-")[0]):
                            compoundPoints += 0.5
                            nonCompoundPoints += 0.5
                        
                        if int(set['Weight']) < int(type['Weight']) - 20:
                            nonCompoundPoints -= 1

                        if set["Reps"] >= maxRep:
                            compoundPoints += 1
                        
                        if set["Reps"] >= int(self.repRangeKey[type["Type"]].split("-")[-1]):
                            nonCompoundPoints+= 1
                        
                        if set["Reps"] >= minRep:
                            compoundPoints += .5
                            
                        if set["Reps"] < int(self.repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints -= 1
                else:
                    compoundPoints -= 2
                    nonCompoundPoints -=2    

            
                if type["Type"] == "Full_Compound":    
                    if compoundPoints >= 4:
                        passFail.append({exercise: ["P", compoundPoints]})
                    elif compoundPoints < 2:
                        passFail.append({exercise: ["F+", compoundPoints]})
                    else:
                        passFail.append({exercise: ["F", compoundPoints]})
                    
                else:
                    if nonCompoundPoints >= 4:
                        passFail.append({exercise: ["P", nonCompoundPoints]})
                    elif nonCompoundPoints <= 2:
                        passFail.append({exercise: ["F+", nonCompoundPoints] })
                    else:
                        passFail.append({exercise: ["F", nonCompoundPoints]})
                        
        print(f" Heres your report card:{passFail}")
        for exercise in passFail:
            exerciseName, grade = next(iter(exercise.items()))
            type = self.db.getTypeOfExercise(exerciseName)
            if type["Type"] == "Full_Compound" and grade[0] == "F":
                holdBack = True
                self.db.setExerciseMoveUpFalse(exerciseName)
            elif grade[0] == "P":
                self.db.setExerciseMoveUpTrue(exerciseName)
            elif grade[0] == "F+":
                self.db.setExerciseMoveUpFalse(exerciseName)
            elif grade[0] == "F":
                self.db.setExerciseMoveUpNeural(exerciseName)
        
        if holdBack:
            return weekCount - 1
        else: 
            return weekCount
                
        
    
    def newDay(self, pastDayWasARestDay=False):
        if not pastDayWasARestDay:
            todaysRoutine = self.cycle.pop(0)
            self.cycle.append(todaysRoutine)
            self.todaysRoutine = todaysRoutine
            self.decideToadysWorkOut(self.repRangeCycle[self.todaysRoutine[0]][0], self.todaysRoutine)
        else:
            self.getTodaysWorkOutMassage(self.repRangeCycle[self.todaysRoutine[0]][0], self.todaysRoutine)
        
    def moveBackChecker(self, weekCount, repRange, routine):
        minRep = int(repRange[routine[0]].split("-")[0])
        maxRep = int(repRange[routine[0]].split("-")[1])
        holdBack = False
        
        for exercise in routine[1]:
            type = self.db.getTypeOfExercise(exercise)
            firstSet = []
                        
            results = self.db.getLastTwoPastSpecificExercise(exercise)
            
            for session in results:
                try:
                    firstSet.append(session["List_of_Workouts"][0]["Sets"][0])        
                except:
                    pass
            
            if firstSet:
                if type["Move_Up"] == MoveUp.UP.value:
                    if firstSet[0]["Reps"] < minRep:
                        if type["Type"] == "Full_Compound":
                            holdBack = True
                        self.db.setExerciseMoveUpFalse(exercise)
                elif type["Move_Up"] == MoveUp.DOWN.value:
                    if firstSet[0]["Reps"] > maxRep:
                        self.db.setExerciseMoveUpTrue(exercise)
            else:
                self.db.setExerciseMoveUpFalse(exercise)
        
        if holdBack:
            return 0
        else: 
            return weekCount
            
            
    
    def openLoop(self):
        startHour = 5
        startMinute = 30
        weekTracker = False
        dayTracker = False
        last_day_processed = None
        print(f"Starting openLoop method. today is {self.cycle[-1]} Tmr is {self.todaysRoutine}")
        while True:
            now = datetime.datetime.now()
            
            if now.weekday() == 0 and now.hour == startHour and now.minute == startMinute and not weekTracker:
                print(f"New week detected. Running weekly logic.")
                for week in self.weekCount:
                    print(f"Processing week: {week} with current count: {self.weekCount[week]}")
                    self.weekCount[week] += 1 
                    print(f"About to run moveUpChecker for {week} with weekCount={self.weekCount[week]}")
                    if  self.weekCount[week] == 1:
                        self.weekCount[week] = self.moveUpChecker(self.weekCount[week], self.repRangeCycle[week], self.routine[self.routineType]["Routine"][week])
                        print(f"moveUpChecker adjusted {week} from {self.weekCount[week]} to {self.weekCount[week]}")
                    elif self.weekCount[week] == 2:
                        self.weekCount[week] = self.moveBackChecker(self.weekCount[week], self.repRangeCycle[week], self.routine[self.routineType]["Routine"][week]) 
                    elif self.weekCount[week] == 4:
                        self.weekCount[week] = self.moveUpChecker(self.weekCount[week], self.repRangeCycle[week], self.routine[self.routineType]["Routine"][week])
                        self.weekCount[week] = 0
                        range = self.repRangeCycle[week].pop(0)
                        self.repRangeCycle[week].append(range)
                        print(f"Rotated rep range cycle for {week}")
                        
                weekTracker = True
                print(f"Weekly logic complete")
                
            # Reset weekly flag on any day other than the first day of the week
            if now.weekday() != 0:
                weekTracker = False
            
            if now.hour == startHour and now.minute == startMinute and (last_day_processed is None or last_day_processed != now.date()):
                print(f"New day detected. Running daily logic.")
                if self.textState.getState():
                    print(f"Received text state as True, scheduling new workout.")
                    self.newDay(pastDayWasARestDay=False)
                    
                else:
                    print(f"No text detected, assuming rest day.")
                    print(f"I See We Resting Now Loser")
                    self.newDay(pastDayWasARestDay=True)
                    
                self.textState.resetTextState()
                last_day_processed = now.date()
                print(f"Daily logic complete. Sleeping for 60 seconds.") 
                time.sleep(60)
            

            time.sleep(10)
    
            
class TextState:
    def __init__(self):
        self._gotText = False
    
    def gotText(self):
        self._gotText = True  
    
    def resetTextState(self):
        self._gotText = False
        
    def getState(self):
        return self._gotText
    
class TextListener:
    def __init__(self, coach, textState, LADY=False):
        self.LADY = LADY
        self.coach = coach
        self.textState = textState
        #Twillo api sends there texts in UTC time have to convert to EST
        self.timeOffset = 5
        self.load_twilio_credentials()
        self.client = Client(self.sid, self.token)
        self.last_checked = datetime.datetime.now()
        self.processed_messages = set()
        self.dayCount = 0 
        
    def load_twilio_credentials(self):
        from dotenv import load_dotenv
        import os
        load_dotenv()
        self.sid = os.environ.get("SID")
        self.token = os.environ.get("token")
        self.twilio_phone_number = os.environ.get("twilloPhoneNumber")
        if self.LADY:
            self.my_phone_number = os.environ.get("ladyPhoneNumber")
        else:
            self.my_phone_number = os.environ.get("myPhoneNumber")
            
    def check_for_incoming_text(self):
        messages = self.client.messages.list(
            to=self.twilio_phone_number,
            date_sent_after=(self.last_checked + datetime.timedelta(hours=self.timeOffset))
        )

        for message in messages:
            print(f"Checking message SID: {message.sid}, From: {message.from_}, Body: {message.body}")
            if message.sid not in self.processed_messages and message.from_ == self.my_phone_number:
                self.processed_messages.add(message.sid)
                self.textState.gotText()
                self.coach.incomingText(message.body)
              
        self.last_checked = datetime.datetime.now()
        self.cleanup_processed_messages()
        
    def cleanup_processed_messages(self):
        if self.dayCount == 2:
            self.dayCount = 0    
            self.processed_messages = set()

    def start_listening(self):
        while True:
            self.check_for_incoming_text()
            time.sleep(10) 


