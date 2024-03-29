import socket
import select
import json
from threading import Thread
import sqlite3
import database

MAX_MSG_LENGTH = 1024
SERVER_PORT = 5555
SERVER_IP = '0.0.0.0'

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
                dic[name] = client_socket #add client to client list

               
#opcode 1 = register request.  opcode 2 = login request.  opcode 3 = workout create. opcode 4 = friend request. opcode 5 = friend accepct.
#opcode 6 = join workout. opcode 7 = leave workout. opcode 8(admin opcode) = delete workout. opcode 9(admin) = user mute for create or join workout. 
#opcode 10(admin) = ban user. opcode 11 = update personal information. opcode 12 = new workout info checkup. opcode 13 = new friend req checkup. 
#opcode 14 = new friend checkup. opcode 15 = scoreboard refresh. opcode 16 = forgot password. opcode 17 = email code checkup. opcode 18 = password reset.
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
                

                elif(opcode == 12): # update personal information
                    myId = msg
                    validWorkoutsIdList = newWorkoutCheckup(curs,myId)
                    workoutList = loadWorkoutInfo(curs,validWorkoutsIdList) # workout list is list of lists of workouts
                    dec = {"name" : sender, "opcode": 12, "msg" : workoutList} 
                    current_socket.send(json.dumps(dec).encode())


def loadWorkoutInfo(curs,validWorkoutsIdList):
    workoutList = []
    for i in validWorkoutsIdList:
        curs.execute(f"SELECT * FROM workout WHERE idforShow ='{i}'") # check if there user with that info exist
        workoutList.append(list(curs.fetchone()))
    return workoutList
def UserInfoForFilter(curs, filters, myId): # get dic of filters take their keys and give back the value of the user for thos filters.
    typeFilter = list(filters.keys())
    myInfoDic = {} # dic with my info for those type of filters
    for i in typeFilter :
        curs.execute(f"SELECT {i} FROM users WHERE idforShow = {myId}" )
        myInfoDic[i] = curs.fetchone()
    return myInfoDic

def newWorkoutCheckup(curs,myId):
    validWorkouts = []
    curs.execute(f"SELECT id, filters FROM workout")
    workouts = curs.fetchall() # list of tuples
    isPrivateWorkout = True 
    for i in workouts: 
        filters = json.loads(i[1]) # choose the filters from the tuple and bring it back to dic by json
        typefilter = list(filters.keys()) # list of the type filter
        myInfoDic = UserInfoForFilter(curs,filters,myId)

        for g in typefilter:

            if(g == "age"):
                if(filters[g] >= myInfoDic["age"]):
                    validWorkouts.append[i[0]] # add workout id
            if(filters[g] == myInfoDic[g]):
                validWorkouts.append[i[0]] # add workout id
    return validWorkouts

def updateInfo(con, curs, myId, typeUpdate, updatedInfo):
    curs.execute(f"UPDATE users SET {typeUpdate} = ? WHERE idforShow = ?", (updatedInfo, myId)) # update user info
    con.commit()
    curs.execute(f"SELECT idforShow, name, last_name, birthdate, gender, region, Email  FROM users WHERE idforShow='{myId}'")
    userInfo = curs.fetchone()
    return userInfo
    

def banUser(con, curs, myId, myName, UserId, UserName):
    curs.execute(f"SELECT isAdmin FROM users WHERE idforShow ='{myId}' AND name = '{myName}' " )
    isAdmin = curs.fetchone() #check if user that request to ban is admin.
    if(isAdmin == 1):
        isBlackList = 1 
        curs.execute(f"UPDATE users SET isBlackList = '{isBlackList}' WHERE idforShow = '{UserId}' AND name = '{UserName}'") # update user that got banned
        con.commit()
        return True
    return False



def muteUser(con, curs, myId, myName, UserId, UserName):
    curs.execute(f"SELECT isAdmin FROM users WHERE idforShow ='{myId}' AND name = '{myName}' " )
    isAdmin = curs.fetchone()
    if(isAdmin == 1):
        isMute = 1 
        curs.execute(f"UPDATE users SET isMute = '{isMute}' WHERE idforShow = '{UserId}' AND name = '{UserName}'")
        con.commit()
        return True
    return False

def deleteWorkout(con, curs,workoutId, workoutCreator, myId, myName):
    curs.execute(f"SELECT isAdmin FROM users WHERE idforShow ='{myId}' AND name = '{myName}' " )
    isAdmin = curs.fetchone()
    if(isAdmin == 1):
        curs.execute(f"DELETE FROM workouts WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}' " )
        con.commit()
        return True
    return False


def removeFromWorkout(con, curs, myId, myName, workoutId, workoutCreator):
    curs.execute(f"SELECT * FROM workouts WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}' ") # check if there workout with that info exist
    exist = curs.fetchone() is not None
    if(exist):
        curs.execute(f"SELECT participants FROM workouts WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}' " )
        participants = curs.fetchone()
        participants = json.dumps(participants)
        del participants[myId]  # delete me from dic
        participants = json.loads(participants) # update workout info 
        curs.execute(f"UPDATE workouts SET participants = '{participants}' WHERE idforShow ='{workoutId}' AND creator = '{workoutCreator}'  ")
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
        friendlist = json.dumps(friendlist)
        friendlist[myId] = myName # add me in my friend, friend list
        friendlist = json.loads(friendlist)
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
        reqList = curs.fetchone()
        reqList = json.dumps(reqList)
        reqList[senderId] = sender
        reqList = json.loads(reqList)
        curs.execute(f"UPDATE users SET reqList = '{reqList}' WHERE idforShow ='{reciverId}' AND name = '{reciver}'  ")
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
