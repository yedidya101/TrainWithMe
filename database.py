import sqlite3
import json

# Connect to the SQLite database

conn = sqlite3.connect('TrainWithMe.db')
c = conn.cursor()

# Create a table for users
def createTables(c):
    c.execute('''CREATE TABLE IF NOT EXIST users
             (id INTEGER PRIMARY KEY,
              idforShow INTEGER UNIQE,
              name TEXT,
              last_name TEXT,
              birthdate TEXT,
              gender TEXT,
              region TEXT,
              Email TEXT,
              Password TEXT,
              friendlist TEXT,
              reqList TEXT,
              isAdmin INTEGER,
              isBlackList INTEGER)''')
# Create a table for workouts
    c.execute('''CREATE TABLE IF NOT EXIST workouts 
             (id INTEGER PRIMARY KEY,
              idforShow INTEGER UNIQE,
              time TEXT,
              location TEXT,
              sport_type TEXT,
              creator TEXT,
              participants TEXT,
              numOfParticipants INTEGER,
              private_workout INTEGER)''')

    
# Define functions to insert data into the tables
def insert_user(user, password, c):
    friendlist = {} 
    reqList = {}
    c.execute("INSERT INTO users (name, last_name, birthdate, gender, region, Email, Password, friendlist, reqList, isAdmin, isBlackList) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (user.Name, user.Last_name, user.Birthdate, user.Gender, user.Region, user.Email, password, friendlist, reqList, 0, 0))
    conn.commit()

def insert_workout(workout, c):
    participants = workout.participant 
    participants = json.loads(participants)
    c.execute("INSERT INTO workouts (time, location, sport_type, creator,participants, numOfParticipants, private_workout) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (workout.time, workout.location, workout.sportType, workout.creator, participants, workout.numOfParticipants, int(workout.PrivateWorkout)))
    conn.commit()


# Example usage:
# Assume you have instantiated user and workout objects
# user_obj = user("John", "Doe", "1990-01-01", "Male", "USA", isAdmin=True, isBlackList=False)
# workout_obj = workout("2024-02-21 10:00", "Park", [], "Running", "John", False)

# Insert data into the tables
# insert_user(user_obj)
# insert_workout(workout_obj)

# Close the connection
conn.close()
