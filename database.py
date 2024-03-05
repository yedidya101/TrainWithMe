import sqlite3
import json
import random
# Connect to the SQLite database

#conn = sqlite3.connect('TrainWithMe.db')
#c = conn.cursor()


# Create a table for users
def createTables(c):
    c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY,
              idforShow TEXT UNIQE,
              name TEXT,
              last_name TEXT,
              birthdate TEXT,
              gender TEXT,
              region TEXT,
              Email TEXT,
              Password TEXT NOT NULL,
              friendlist TEXT,
              reqList TEXT,
              isAdmin INTEGER DEFAULT 0,
              isMute INTEGER DEFAULT 0,
              isBlackList INTEGER DEFAULT 0)''')
# Create a table for workouts
    c.execute('''CREATE TABLE IF NOT EXISTS workouts
             (id INTEGER PRIMARY KEY,
              idforShow INTEGER UNIQE,
              time TEXT,
              location TEXT,
              sport_type TEXT,
              creator TEXT,
              PublicIDcreator TEXT,
              participants TEXT,
              filters TEXT,
              numOfParticipants INTEGER,
              private_workout INTEGER)''')


def getUniqueIDforUsers(curs):
    IdNotTwice = True
    while(IdNotTwice):
        random_number = random.randint(0, 9999)
        publicID = '{:04d}'.format(random_number)
        curs.execute(f"SELECT * FROM users WHERE idforShow ='{publicID}'")
        exist = curs.fetchone() is not None
        if(not exist):
            return publicID
        curs.fetchall()

def getUniqueIDForWorkout(curs):
    IdNotTwice = True
    while(IdNotTwice):
        random_number = random.randint(0, 9999)
        publicID = '{:04d}'.format(random_number)
        curs.execute(f"SELECT * FROM workouts WHERE idforShow ='{publicID}'")
        exist = curs.fetchone() is not None
        if(not exist):
            return publicID
        curs.fetchall()

# Define functions to insert data into the tables
def insert_user(user, password, conn, c):
    friendlist = json.dumps({})
    reqList = json.dumps({})
    
    c.execute("""INSERT INTO users (idforShow, name, last_name, birthdate, gender, region, Email, friendlist,
               reqList, Password) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (user.publicID, user.Name, user.Last_name, user.Birthdate, user.Gender, user.Region, user.Email, friendlist, reqList, password))
    conn.commit()

def insert_workout(workout, conn, c):
    participants = workout.participant # dic of key is id and value is name
    participants = json.loads(participants)
    filters = workout.filters # dic of key is type of filter and value is what border for the filter. example: filters[age] = 45
    filters = json.loads(filters)
    c.execute("INSERT INTO workouts (idforShow, time, location, sport_type, creator, PublicIDcreator, participants, filters, numOfParticipants, private_workout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (workout.idforShow, workout.time, workout.location, workout.sportType, workout.creator,workout.PublicIDcreator, filters, participants, workout.numOfParticipants, int(workout.PrivateWorkout)))
    conn.commit()


# Example usage:
# Assume you have instantiated user and workout objects
# user_obj = user("John", "Doe", "1990-01-01", "Male", "USA", isAdmin=True, isBlackList=False)
# workout_obj = workout("2024-02-21 10:00", "Park", [], "Running", "John", False)

# Insert data into the tables
# insert_user(user_obj)
# insert_workout(workout_obj)

# Close the connection
#conn.close()
