from pymongo import MongoClient
from dotenv import load_dotenv 
import os
import json
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import datetime
import time
import threading


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
    
    def getJson(self):
        return {"Date":self.date, "List_of_Workouts":[w.getJson() for w in self.workouts], "Rating": self.rating, "Day":self.day}
    
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
        return int(self.weight)
    
    def getReps(self):
        return int(self.reps)
    
    def getJson(self):
        return {"Weight":int(self.weight), "Reps":int(self.reps)}
        
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
        if type(workout) == Session:
            self.workOutsCollection.insert_one(workout.getJson())
            
    
    
    def postNewWorkOut(self, name, type, moveUp):
        moveUp = int(moveUp)
        result = self.exerciseCollection.find_one({"Name":name})
        if not result:
            self.exerciseCollection.insert_one({"Name":name, "Type": type, "Move_Up_Rate": moveUp, "Move_Up": False})
        else:
            print(f"{name} is already in the database updating it")
            self.exerciseCollection.replace_one({"Name":name}, {"Name":name, "Type": type, "Move_Up_Rate": moveUp, "Move_Up": False}, True)
        
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
    restDay = False
    repRangeKey = {}
    startingPercentage = 0.82
    db = DBController()
    routine = None
    routineFile = "routine.json"
    day = None
    todaysRoutine = {}
    
    
    def __init__(self):
        self.loadInRoutine()
        self.cycle = [["Pull",self.routine["Pull"]], ["Push",self.routine["Push"]], ["Legs",self.routine["Legs"]]]
        self.pullRepRangeCycle = ["6-8", "4-6", "2-4"]
        self.pushRepRangeCycle = ["6-8", "4-6", "2-4"]
        self.legsRepRangeCycle = ["6-8", "4-6", "2-4"]
        self.repRangeKey = {"Full_Compound": "4-8", "Semi_Compound": "6-8", "Non_Compound":"10-15", "Body_Weight": "7-12"}
        self.todaysRoutine = self.cycle.pop(0)
        self.cycle.append(self.todaysRoutine)
        self.day = self.cycle[0][0]
                
    def loadInRoutine(self):
        with open(self.routineFile, 'r') as file:
            self.routine = json.load(file)

    def changeExerciseInRoutine(self, day, old, new):
        moveUp = 10
        type = "Non_Compound"
        routine = None
        
        if "(" in new and ")" in new:
            split = new.split("(")
            new = split[0]
            split = split[1].replace(")", "").split(",")
            type = split[0]
            if len(split) > 1:
                moveUp = split[1]
        else:
            print("Not the right format for adding new exersie")
        
        
        self.db.postNewWorkOut(new, type, moveUp)  
        
        with open(self.routineFile, 'r') as file:
            routine = json.load(file)
        
        for i in range(len(routine[day])):
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
    
    def setRestDay(self):
        self.restDay = True 
    
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
        workoutPlan = self.cycle[-1] 
        session = None
        nextOne = True
        name = None
        rating = -1
        weight = None
        reps = None
        text = text.replace(f"Message from {os.environ.get('myPhoneNumber')}:", "")
        splitText = text.split("\n")
        i = 0
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
                            workouts.append(Workout(workoutPlan[-1][i], sets))
                            sets = []
                            i += 1
                    i += 1
                    continue
        
                if ":" in t:
                    if name:
                        if "*" in name[0]:
                            self.changeExerciseInRoutine(workoutPlan[0], workoutPlan[-1][i], name.replace("*", ""))
                            workoutPlan = self.cycle[-1]
                            
                        if sets:
                            workouts.append(Workout(workoutPlan[-1][i], sets))
                            sets = []
                            i += 1
                    index = t.find(":")
                    if index != -1:
                        name = t[:index]
                else:
                    tempSplit = t.split("x")
                    if tempSplit:
                        weight = tempSplit[0]
                        reps = tempSplit[1]
                        sets.append(Set(weight, reps))
                
        
        if name:
            if "*" in name[0]:
                self.changeExerciseInRoutine(workoutPlan[0], workoutPlan[-1][i], name.replace("*", ""))
                workoutPlan = self.cycle[-1]
            if sets:
                workouts.append(Workout(workoutPlan[-1][i], sets))
                sets = []
            
        session = Session(workouts, datetime.datetime.today(), int(rating), workoutPlan[0])
        
        self.db.postWorkOut(session)
        return session
    
    
    def loadInNewWorkouts(self, file):
        self.db.loadInExercises(file)
    
    def moveUpChecker(self, weekCount, repRange, routine):
        minRep = int(repRange.split("-")[0])
        maxRep = int(repRange.split("-")[1])
        holdBack = False
        passFail = []
        
        for exercise in routine[1]:
            type = self.db.getTypeOfExercise(exercise)
            compoundPoints = 0
            nonCompoundPoints = 0
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
                            
                        if set["Reps"] >= int(self.repRangeKey[type["Type"]].split("-")[0]):
                            nonCompoundPoints += 1
                            
                        if set["Reps"] < int(self.repRangeKey[type["Type"]].split("-")[0]):
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
                    if compoundPoints < 3:
                        print(f"Failed")
                        passFail.append({exercise: "F"})
                    else:
                        print("Pass")
                        passFail.append({exercise: "P"})
                    
                else:
                    if nonCompoundPoints < 3:
                        print(f"Failed")
                        passFail.append({exercise: "F"})
                    else:
                        print("Pass")
                        passFail.append({exercise: "P"})
                        
        print(passFail)
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
        pullRepRange = self.pullRepRangeCycle.pop(0)
        self.pullRepRangeCycle.append(pullRepRange)
        
        pushRepRange = self.pushRepRangeCycle.pop(0)
        self.pushRepRangeCycle.append(pushRepRange)
        
        legsRepRange = self.legsRepRangeCycle.pop(0)
        self.legsRepRangeCycle.append(legsRepRange)

        return pullRepRange, pushRepRange, legsRepRange
    
    def newDay(self, pushRepRange, pullRepRange, legsRepRange, todaysRoutine):
        if self.restDay:
            self.restDay = False
            return todaysRoutine
        else:
            if todaysRoutine[0] == "Push":
                self.decideToadysWorkOut(pushRepRange, todaysRoutine)
            elif todaysRoutine[0] == "Pull":
                self.decideToadysWorkOut(pullRepRange, todaysRoutine)
            else:
                self.decideToadysWorkOut(legsRepRange, todaysRoutine)
                
            todaysRoutine = self.cycle.pop(0)
            self.cycle.append(todaysRoutine)
            return todaysRoutine
    
    def openLoop(self):
        startHour = 5
        startMinute = 30
        weekTracker = False 
        pullWeekCount = 0
        pushWeekCount = 0
        legsWeekCount = 0
        dayTracker = False
        pullRepRange, pushRepRange, legsRepRange = self.cycleAllRepRanges()
        while True:
            now = datetime.datetime.now()
            
            if now.weekday() == 0 and now.hour == startHour and now.minute == startMinute and not weekTracker:
                if pullWeekCount == 1:
                    pullWeekCount = self.moveUpChecker(pullWeekCount, pullRepRange, self.todaysRoutine)
                elif pullWeekCount == 3:
                    pullWeekCount = self.moveUpChecker(pullWeekCount, pullRepRange, self.todaysRoutine)
                elif pullWeekCount == 4:
                    pullWeekCount = 0
                    pullRepRange = self.pullRepRangeCycle.pop(0)
                    self.pullRepRangeCycle.append(pullRepRange)
                    
                
                if pushWeekCount == 1:
                    pushWeekCount = self.moveUpChecker(pushWeekCount, pushRepRange, self.todaysRoutine)
                elif pushWeekCount == 3:
                    pushWeekCount = self.moveUpChecker(pushWeekCount, pushRepRange, self.todaysRoutine)
                elif pushWeekCount == 4:
                    pushWeekCount = 0
                    pushRepRange = self.pushRepRangeCycle.pop(0)
                    self.pushRepRangeCycle.append(pushRepRange)
                
                
                if legsWeekCount == 1:
                    legsWeekCount = self.moveUpChecker(legsWeekCount, legsRepRange, self.todaysRoutine)
                elif legsWeekCount == 3:
                    legsWeekCount = self.moveUpChecker(legsWeekCount, legsRepRange, self.todaysRoutine)
                elif legsWeekCount == 4:
                    legsWeekCount = 0
                    legsRepRange = self.legsRepRangeCycle.pop(0)
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
                self.todaysRoutine = self.newDay(pushRepRange, pullRepRange, legsRepRange, self.todaysRoutine)
                dayTracker = True
                time.sleep(60)
            
            if now.hour == 0 and now.minute == 0:
                dayTracker = False
                
            time.sleep(10)


class TextListener:
    def __init__(self, coach):
        self.coach = coach
        self.load_twilio_credentials()
        self.client = Client(self.sid, self.token)
        self.last_checked = datetime.datetime.now()
        self.processed_messages = {}
        self.message_received_today = False
        self.started_listening = False  
        
    def load_twilio_credentials(self):
        from dotenv import load_dotenv
        import os
        load_dotenv()
        self.sid = os.environ.get("SID")
        self.token = os.environ.get("token")
        self.twilio_phone_number = os.environ.get("twilloPhoneNumber")
        self.my_phone_number = os.environ.get("myPhoneNumber")
    
    def check_for_incoming_text(self):
        messages = self.client.messages.list(
            to=self.twilio_phone_number,
            date_sent_after=self.last_checked
        )

        for message in messages:
            if self.started_listening and message.sid not in self.processed_messages and message.from_ == self.my_phone_number:
                self.processed_messages[message.sid] = datetime.datetime.now()
                self.message_received_today = True
                if self.started_listening:                
                    self.coach.incomingText(message.body)
                    print(f"Processed message: {message.body}")
                else:
                    self.started_listening = True  # Set flag to indicate listener is now ready
                    print("Listener is now actively processing new messages.")

        self.last_checked = datetime.datetime.now()
        self.processed_messages[message.sid] = datetime.datetime.now()
        
    def cleanup_processed_messages(self):
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=48)
        self.processed_messages = {sid: timestamp for sid, timestamp in self.processed_messages.items() if timestamp > cutoff_time}
        

    def manage_daily_routine(self):
        now = datetime.datetime.now()
        if now.hour == 4 and now.minute == 0:
            if not self.message_received_today:
                print("No text received today. Assuming it was a rest day.")
                self.coach.setRestDay() 

            self.message_received_today = False
            time.sleep(60)

    def start_listening(self):
        while True:
            self.check_for_incoming_text()
            self.manage_daily_routine()
            time.sleep(10) 



if __name__ == "__main__":
    coach = Coach()
    listener = TextListener(coach)

    coach_thread = threading.Thread(target=coach.openLoop, daemon=True)
    listener_thread = threading.Thread(target=listener.start_listening, daemon=True)

    coach_thread.start()
    listener_thread.start()

    coach_thread.join()
    listener_thread.join()  
