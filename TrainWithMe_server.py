import socket
import select
import json
from threading import Thread
import sqlite3
import database
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

MAX_MSG_LENGTH = 1024
SERVER_PORT = 5555
SERVER_IP = '0.0.0.0'
print ("howw")
def server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_IP, SERVER_PORT))
    server_socket.listen()
    client_sockets = []
    print("Listening for clients...")
    LookForClientsAndData(server_socket, client_sockets)

def GetInfo(Clientsock):
    data = Clientsock.recv(MAX_MSG_LENGTH).decode()
    try:
        dec = json.loads(data)
    except (TypeError, json.decoder.JSONDecodeError):
        return False
    return dec


def LookForClientsAndData(serverSocket, clientSocket):
    dic = {}
    con = sqlite3.connect('TrainWithMe.db')
    curs = con.cursor()
    database.createTables(curs)
    mutedList = []
    while True:
        ready_to_read, ready_to_write, in_error = select.select([serverSocket] + clientSocket, [], [])
        for current_socket in ready_to_read:
            if current_socket is serverSocket:
                (client_socket,client_address) = current_socket.accept()
                print("New client joined!" , client_address)
                clientSocket.append(client_socket)
                name = client_socket.recv(MAX_MSG_LENGTH).decode().lstrip()
                print(name)
                dic[name] = client_socket #add client to client list

               
#opcode 1 = register request.  opcode 2 = login request.  opcode 3 = workout create. opcode 4 = friend request. opcode 5 = friend accepct.
#opcode 6 = join workout. opcode 7 = leave workout. opcode 8(admin opcode) = delete workout. opcode 9(admin) = user mute for create or join workout. 
#opcode 10(admin) = ban user. opcode 11 = update personal information. opcode 12 = new workout info checkup. opcode 13 = new friend req checkup. 
#opcode 14 = new friend checkup. opcode 15 = scoreboard refresh. opcode 16 = forgot password. opcode 17 = password reset.
            else:
                dec = GetInfo(current_socket)
                if not dec:
                    continue
                sender = dec["name"]
                opcode = dec["opcode"]
                msg = dec["msg"]

                if(opcode == 1): # register request
                    userList = msg.split(',')
                    password = userList.pop()
                    print(userList)
                    publicID = database.getUniqueIDforUsers(curs)
                    newUser = user(*userList, publicID) 
                    status, client = Register(con, curs, newUser, password) #try to register new user. if exist, status = false if not exist status = true and user have been added
                    if(status):
                        msg = json.dumps(client)

                    else:
                        #msg = "error occured"
                        msg = json.dumps(client)
                    dec = {"name" : sender, "opcode": 1, "msg" : msg }
                    current_socket.send(json.dumps(dec).encode())
                    con.close()

                elif(opcode == 2): # login request
                    userList = msg.split(',') # info from msg that client send, include password and Email with "," bettwen them
                    password = userList.pop()
                    Email = userList.pop()
                    User = Login(con, curs, Email, password) # ask data base to see if there is an exist account and if exist give info and create user obj
                    if(User == None):
                        msg = "Login failed "
                    else:
                        msg = user.__str__() # converte user info into str for sending

                    dec = {"name" : sender, "opcode": 2, "msg" : msg }
                    current_socket.send(json.dumps(dec).encode())

                elif(opcode == 3): # workout creation
                    workoutlist = msg.split(',')
                    creatorId = workoutlist.pop()
                    creatorName = workoutlist.pop()
                    curs.execute(f"SELECT isMute FROM users WHERE idforShow ='{creatorId}' AND name = '{creatorName}' " ) # check if user not muted
                    IsMute = curs.fetchone()
                    if(IsMute != 1):
                        publicID = database.getUniqueIDForWorkout(curs)
                        newWorkout = workout(*workoutlist, creatorId, creatorName, publicID )
                        createWorkout(con, curs, workout)
                        msg = "workout has been added"
                    else:
                        msg = "you are muted from creating workout. the workout has not created."
                    dec = {"name" : sender, "opcode": 3, "msg" : msg }
                    current_socket.send(json.dumps(dec).encode())
                  
                elif(opcode == 4): # friend request creation
                    friendRq = msg.split(",")
                    senderId = friendRq[0]
                    sender =  friendRq[1]
                    reciverId = friendRq[2]
                    reciver = friendRq[3]
                    sendReq = friendReq(con, curs, sender, senderId, reciver, reciverId)
                    if(sendReq): # if the req have been sent successfully
                        msg = "friend request have been sent."
                        dec = {"name" : sender, "opcode": 4, "msg" : msg }
                    else: 
                        msg = "user not exist."
                        dec = {"name" : sender, "opcode": 4, "msg" : msg }
                    current_socket.send(json.dumps(dec).encode())

                elif(opcode == 5): # accept friend request
                    friendInfo = msg.split(",")
                    myId = friendInfo[0]
                    myName = friendInfo[1]
                    newFriendId =  friendInfo[2]
                    newFriendName = friendInfo[3]
                    updatedFriendList = acceptReq(con, curs, myId, myName, newFriendId, newFriendName) # set new friend in both users friend lists
                    msg = updatedFriendList
                    dec = {"name" : sender, "opcode": 5, "msg" : msg } # return updated friend list.
                    current_socket.send(json.dumps(dec).encode())

                elif(opcode == 6): # join workout
                    workoutInfo = msg.split(",")
                    myId = workoutInfo[0]
                    myName = workoutInfo[1]
                    workoutCreator = workoutInfo[2]
                    workoutId = workoutInfo[3]
                    addedToWorkout = joinWorkout(con, curs, myId, myName, workoutId, workoutCreator) # add me to participants list.
                    if(addedToWorkout):
                        msg = "Added To The Workout Successfully. "
                    else: 
                        msg = "An error occurred, you are not added to the workout"
                    dec = {"name" : sender, "opcode": 6, "msg" : msg } 
                    current_socket.send(json.dumps(dec).encode())

                elif(opcode == 7): # leave workout
                    workoutInfo = msg.split(",")
                    myId = workoutInfo[0]
                    myName = workoutInfo[1]
                    workoutCreator = workoutInfo[2]
                    workoutId = workoutInfo[3]
                    isRemoved = removeFromWorkout(con, curs, myId, myName, workoutId, workoutCreator)
                    if(isRemoved):
                        msg = "You have been removed from this workout."
                    else:
                        msg = "An error occurred, you are not removed from the workout"
                    dec = {"name" : sender, "opcode": 7, "msg" : msg } 
                    current_socket.send(json.dumps(dec).encode())

                elif(opcode == 8): # delete workout
                    workoutInfo = msg.split(",")
                    myId = workoutInfo[0]
                    myName = workoutInfo[1]
                    workoutCreator = workoutInfo[2]
                    workoutId = workoutInfo[3]
                    isWorkoutRemoved = deleteWorkout(con, curs,workoutId, workoutCreator, myId, myName)
                    if(isWorkoutRemoved):
                        msg = "Workout removed."
                    else:
                        msg = "You are not an admin"

                    dec = {"name" : sender, "opcode": 8, "msg" : msg } 
                    current_socket.send(json.dumps(dec).encode())

                elif(opcode == 9): # muteUser
                    muteInfo = msg.split(",")
                    myId = muteInfo[0]
                    myName = muteInfo[1]
                    UserId = muteInfo[2]
                    UserName = muteInfo[3]
                    gotMute = muteUser(con, curs, myId, myName, UserId, UserName)
                    if(gotMute):
                        msg = "The User has muted."
                    else: 
                        msg = "Error occurd, the user was not muted."
                    dec = {"name" : sender, "opcode": 9, "msg" : msg } 
                    current_socket.send(json.dumps(dec).encode())

                elif(opcode == 10): # ban user
                    banInfo = msg.split(",")
                    myId = banInfo[0]
                    myName = banInfo[1]
                    UserId = banInfo[2]
                    UserName = banInfo[3]
                    gotBan = banUser(con, curs, myId, myName, UserId, UserName)
                    if(gotBan):
                        msg = "The User has banned."
                    else: 
                        msg = "Error occurd, the user was not banned."
                    dec = {"name" : sender, "opcode": 9, "msg" : msg } 
                    current_socket.send(json.dumps(dec).encode())
                
                elif(opcode == 11): # update personal information
                    dataList = msg.split(",")
                    myId = dataList[0]
                    typeUpdate = dataList[1]
                    updatedInfo = dataList[2]
                
                    userInfo = updateInfo(con, curs, myId, typeUpdate, updatedInfo)
                    dec = {"name" : sender, "opcode": 11, "msg" : userInfo } 
                    current_socket.send(json.dumps(dec).encode())
                

                elif(opcode == 12): # new workouts checkup
                    myId = msg
                    validWorkoutsIdList = newWorkoutCheckup(curs,myId)
                    WorkoutDicList = loadWorkoutDicList(curs, validWorkoutsIdList)
                    dec = {"name" : sender, "opcode": 12, "msg" : WorkoutDicList} 
                    current_socket.send(json.dumps(dec).encode())


                elif(opcode == 13): # avilable freind req checkup
                    myId = msg
                    reqList = freindReqDec(curs, myId)
                    dec = {"name" : sender, "opcode": 13, "msg" : reqList} 
                    current_socket.send(json.dumps(dec).encode())


                elif(opcode == 14):
                    myId = msg
                    freindListDec = freindListCheckup(curs, myId)
                    dec = {"name" : sender, "opcode": 13, "msg" : freindListDec} 
                    current_socket.send(json.dumps(dec).encode())
                
                elif(opcode == 15):
                    pass

                elif(opcode == 16): #get email from user and send reset code to email and send back to user code the reset code for checking  
                    Email = msg
                    resetCode = request_reset_code(curs, Email, client_socket)
                    dec = {"name" : sender, "opcode": 16, "msg" : resetCode} 

                elif(opcode == 17): # update new password
                    dataList = msg.split(",")
                    newPassword = dataList[0]
                    myId = dataList[1]
                    userInfo = updateInfo(con, curs, myId, "Password", newPassword)
                    dec = {"name" : sender, "opcode": 17, "msg" : "password has changed."} 
                    

def request_reset_code( cursor, Email, client_socket):
    global reset_code
    ErrorMsg = "Error happend sending code"
    try:
        # Check if the user with the given email exists
        cursor.execute("SELECT * FROM users WHERE email=?", (Email,))
        user = cursor.fetchone()

        if user:
            # Generate and send reset code
            reset_code = str(random.randint(100000, 999999))

            sender_email = "trainwithmeapplication@gmail.com"
            app_password = "trtm elxy bueh zlvd"
            subject = "Password Reset Code"
            body = f"Your password reset code is: {reset_code}"

            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = Email
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain"))

            try:
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.starttls()
                    server.login(sender_email, app_password)
                    server.sendmail(sender_email, Email, message.as_string())

                return reset_code
            except Exception as e:
                print(f"Error sending email: {e}")
                return ErrorMsg
        else:
            return reset_code
    except Exception as e:
        print(f"Error requesting reset code: {e}")
        return ErrorMsg


def getScoreBoard(curs):
    scoreBoardDic = {}
    curs.execute(f"SELECT top10, top10Score FROM users scoreboard" )
    scoreBoard = curs.fetchone()
    top10 = json.loads(scoreBoard[0]) # dic of keys as places in top 10 and id + name as values and include key month and value of the current month
    top10Score = json.loads(scoreBoard[1])# dic of keys as places in top 10 and score of the current place as value.
    return top10, top10Score

def freindListCheckup(curs, myId):
    curs.execute(f"SELECT friendlist FROM users WHERE idforShow = {myId} " )
    friendslist = json.loads(curs.fetchone()[0]) # return from data base tuple of json of req list dec and make it back to dictypeFilter
    return friendslist


def freindReqDec(curs, myId):
    curs.execute(f"SELECT reqList FROM users WHERE idforShow = {myId} " )
    reqList = json.loads(curs.fetchone()[0]) # return from data base tuple of json of req list dec and make it back to dictypeFilter
    return reqList

def loadWorkoutDicList(curs, idList): # loads into dic workout information and making list of workout dic
    workoutDic = {} # dic of workout
    WorkoutDicList = [] # list of dic of workouts
    for i in idList:
        curs.execute(f"SELECT time, location, sport_type, creator, PublicIDcreator, participants, numOfParticipants FROM workouts WHERE idforShow = {i}" )
        workoutTuple = curs.fetchone()
        workoutDic["time"] = workoutTuple[0]
        workoutDic["location"] = workoutTuple[1]
        workoutDic["sport_type"] = workoutTuple[2]
        workoutDic["creator"] = workoutTuple[3]
        workoutDic["PublicIDcreator"] = workoutTuple[4]
        workoutDic["participants"] = workoutTuple[5]
        workoutDic["numOfParticipants"] = workoutTuple[6]
        WorkoutDicList.append(workoutDic)# add to the dic list current workout
    return WorkoutDicList # fully information on relevant workouts

#def loadWorkoutInfo(curs,validWorkoutsIdList):
#    workoutList = []
#    for i in validWorkoutsIdList:
#        curs.execute(f"SELECT * FROM workout WHERE idforShow ='{i}'") # check if there user with that info exist
#        workoutList.append(list(curs.fetchone()))
#    return workoutList

def UserInfoForFilter(curs, typeFilter, myId): # get dic of filters take their keys and give back the value of the user for thos filters.
    myInfoDic = {} # dic with my info for those type of filters
    for i in typeFilter : #typeFilter is list of type of filters
        curs.execute(f"SELECT {i} FROM users WHERE idforShow = {myId}" )
        myInfoDic[i] = curs.fetchone()[0]
    return myInfoDic

def newWorkoutCheckup(curs,myId):
    validWorkoutsID = []
    curs.execute(f"SELECT id, filters FROM workout")
    workouts = curs.fetchall() # list of tuples
    isPrivateWorkout = True 
    for i in workouts: 
        filters = json.loads(i[1]) # choose the filters from the tuple and bring it back to dic by json
        typefilter = list(filters.keys()) # list of the type filter
        myInfoDic = UserInfoForFilter(curs,filters,myId)

        for g in typefilter:
            if(g == "age"):
                if(filters[g] >= myInfoDic[g]):
                    validWorkoutsID.append[i[0]] # add workout id
            if(filters[g] == myInfoDic[g]):
                validWorkoutsID.append[i[0]] # add workout id
    return validWorkoutsID

def updateInfo(con, curs, myId, typeUpdate, updatedInfo): # update info in user information
    curs.execute(f"UPDATE users SET {typeUpdate} = ? WHERE idforShow = ?", (updatedInfo, myId)) # update user info
    con.commit()
    curs.execute(f"SELECT idforShow, name, last_name, birthdate, gender, region, Email  FROM users WHERE idforShow='{myId}'")
    userInfo = list(curs.fetchone())
    return userInfo
    

def banUser(con, curs, myId, myName, UserId, UserName):
    curs.execute(f"SELECT isAdmin FROM users WHERE idforShow ='{myId}' AND name = '{myName}' " )
    isAdmin = curs.fetchone() #check if user that request to ban is admin.
    isAdmin = isAdmin[0]
    if(isAdmin == 1):
        isBlackList = 1 
        curs.execute(f"UPDATE users SET isBlackList = '{isBlackList}' WHERE idforShow = '{UserId}' AND name = '{UserName}'") # update user that got banned
        con.commit()
        return True
    return False



def muteUser(con, curs, myId, myName, UserId, UserName):
    curs.execute(f"SELECT isAdmin FROM users WHERE idforShow ='{myId}' AND name = '{myName}' " )
    isAdmin = curs.fetchone()
    isAdmin = isAdmin[0]
    if(isAdmin == 1):
        isMute = 1 
        curs.execute(f"UPDATE users SET isMute = '{isMute}' WHERE idforShow = '{UserId}' AND name = '{UserName}'")
        con.commit()
        return True
    return False

def deleteWorkout(con, curs,workoutId, workoutCreator, myId, myName):
    curs.execute(f"SELECT isAdmin FROM users WHERE idforShow ='{myId}' AND name = '{myName}' " )
    isAdmin = curs.fetchone()
    isAdmin = isAdmin[0]
    if(isAdmin == 1):
        curs.execute(f"DELETE FROM workouts WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}' " )
        con.commit()
        return True
    return False


def removeFromWorkout(con, curs, myId, myName, workoutId, workoutCreator):
    curs.execute(f"SELECT * FROM workouts WHERE idforShow = {workoutId} AND creator = {workoutCreator} ") # check if there workout with that info exist
    exist = curs.fetchone() is not None
    if(exist):
        curs.execute(f"SELECT participants FROM workouts WHERE idforShow ={workoutId} AND creator = {workoutCreator} " )
        participants = curs.fetchone()
        participants = json.loads(participants[0])
        del participants[myId]  # delete me from dic
        participants = json.dumps(participants) # update workout info 
        curs.execute(f"UPDATE workouts SET participants = {participants} WHERE idforShow ={workoutId} AND creator = {workoutCreator}  ")
        con.commit()

        curs.execute(f"SELECT numOfParticipants FROM workouts WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}' " )
        numOfParticipants = curs.fetchone()
        numOfParticipants -= 1
        curs.execute(f"UPDATE workouts SET numOfParticipants = '{numOfParticipants}' WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}'  ") # update number of participants.
        con.commit()
        return True
    return False


def joinWorkout(con, curs, myId, myName, workoutId, workoutCreator):
    curs.execute(f"SELECT * FROM workouts WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}' ") # check if there workout with that info exist
    exist = curs.fetchone() is not None
    if(exist):
        curs.execute(f"SELECT isMute FROM users WHERE idforShow ='{myId}' AND name = '{myName}' " ) # check if user not muted
        isMute = curs.fetchone()
        isMute = isMute[0]
        if(isMute != 1):
            curs.execute(f"SELECT participants FROM workouts WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}' " )
            participants = curs.fetchone()
            participants = json.dumps(participants)
            participants[myId] = myName
            participants = json.loads(participants) # update workout info 
            curs.execute(f"UPDATE workouts SET participants = '{participants}' WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}'  ")
            con.commit()

            curs.execute(f"SELECT numOfParticipants FROM workouts WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}' " )
            numOfParticipants = curs.fetchone() 
            numOfParticipants += 1
            curs.execute(f"UPDATE workouts SET numOfParticipants = '{numOfParticipants}' WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}'  ") # update number of participants.
            con.commit()
            return True
    return False

def acceptReq(con, curs, myId, myName, newFriendId, newFriendName):
        #update my new freind list
        curs.execute(f"SELECT friendlist FROM users WHERE idforShow ='{newFriendId}' AND name = '{newFriendName}' " )
        friendlist = curs.fetchone()
        friendlist = json.loads(friendlist[0])
        friendlist[myId] = myName # add me in my friend, friend list
        friendlist = json.dumps(friendlist)
        curs.execute(f"UPDATE users SET friendlist = '{friendlist}' WHERE idforShow ='{newFriendId}' AND name = '{newFriendName}'  ")
        con.commit()

        #update freind list for my user in data base
        curs.execute(f"SELECT friendlist FROM users WHERE idforShow ='{myId}' AND name = '{myName}' " )
        friendlist = curs.fetchone()
        friendlist = json.dumps(friendlist)
        friendlist[newFriendId] = newFriendName # add my friend in my friend list
        friendlist = json.loads(friendlist)
        curs.execute(f"UPDATE users SET friendlist = '{friendlist}' WHERE idforShow ='{myId}' AND name = '{myName}'  ")
        con.commit()
        return friendlist # the friend request have been sent successfully


def friendReq(con, curs, sender, senderId, reciver, reciverId):
    curs.execute(f"SELECT * FROM users WHERE idforShow ='{reciverId}' AND name = '{reciver}' ") # check if there user with that info exist
    exist = curs.fetchone() is not None
    if(exist):
        #for the reciver of the friend request
        curs.execute(f"SELECT reqList FROM users WHERE idforShow ='{reciverId}' AND name = '{reciver}' " )
        reqList = curs.fetchone()# reqList = tuple that first index is json of dec reqList
        reqList = json.loads(reqList[0]) 
        reqList[senderId] = sender
        reqList = json.dumps(reqList)
        curs.execute(f"UPDATE users SET reqList = {reqList} WHERE idforShow ='{reciverId}' AND name = '{reciver}'  ")
        con.commit()
        return True # the friend request have been sent successfully
    return False # the user that the client gave to send friend req for is not exist

def Register(con, curs, user, password):
    #check if user exist
    testFlag = False
    curs.execute(f"SELECT * FROM users WHERE Email='{user.Email}'")
    exist = curs.fetchone() is not None
    if(not exist):
        testFlag = True
        database.insert_user(user, password, con, curs) # create user
    curs.execute(f"SELECT * FROM users WHERE Email='{user.Email}' AND password = '{password}'")
    client = curs.fetchone()
    return testFlag, client

def Login(con, curs, Email, password):
    curs.execute(f"SELECT * FROM users WHERE Email='{Email}' AND Password = '{password}' ")
    userInfo = curs.fetchone()
    userInfo = list(userInfo)
    userInfo = userInfo[:-4] # remove last 3 cells from is admin is blacklist is mute and password to create user obj
    newUser = user(*userInfo) 
    return newUser

def createWorkout(con, curs,workout):
     database.insert_workout(workout,con, curs)


class workout:
    def __init__(workout, time, location, sportType, participants, filters, numOfParticipants, PrivateWorkout, PublicIDcreator,creator, idforShow):
        workout.time = time # string hour
        workout.location = location # prob text index need to check
        workout.participant = participants 
        workout.sportType = sportType #string
        workout.creator = creator #string
        workout.PrivateWorkout = PrivateWorkout #boolean true of false
        workout.numOfParticipants = numOfParticipants #int
        workout.PublicIDcreator = PublicIDcreator # string
        workout.filters = filters
        workout.idforShow = idforShow
class user: 
    def __init__(info, Name, Last_name, Birthdate, Gender, Region, Email, publicID):
        info.Name = Name # string
        info.Last_name = Last_name # string
        info.Birthdate = Birthdate # text or int need to check in client
        info.Gender = Gender # string
        info.Region = Region # string
        info.Email = Email # string
        info.publicID = publicID # string
        
    def __str__(self):
        return F"{self.Name}, {self.Last_name}, {self.Birthdate}, {self.Gender}, {self.Region}, {self.Email}"
    
def main():
    server()



if __name__ == "__main__":
    main()