import mysql.connector

# Database credentials
db_config = {
    'host': 'sql12.freesqldatabase.com',  
    'user': 'sql12767687',  
    'password': '9z48jQ71yt',
    'database': 'sql12767687'
}

# ✅ Fetch Voter Data with Booth Info
def fetch_voter_data(connection):
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT v.id, v.name, v.dob, v.gender, v.phone, v.aadhar, v.voterId, v.imagePath, v.constitution, 
                   b.booth_id, b.constituency
            FROM voter v
            LEFT JOIN booth b ON v.booth_id = b.booth_id
        """)
        rows = cursor.fetchall()

        print("\n=== Voter Data ===")
        for row in rows:
            print(f"ID: {row[0]}, Name: {row[1]}, DOB: {row[2]}, Gender: {row[3]}, Phone: {row[4]}, "
                  f"Aadhar: {row[5]}, Voter ID: {row[6]}, Image Path: {row[7]}, Constitution: {row[8]}, "
                  f"Booth ID: {row[9] or 'N/A'}, Booth Constituency: {row[10] or 'N/A'}")

    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")

    finally:
        cursor.close()


# ✅ Fetch Candidate Data with Booth Info
def fetch_candidate_data(connection):
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT c.id, c.name, c.dob, c.gender, c.phone, c.aadhar, c.constitution, c.contestType, 
                   c.partyName, c.imagePath, c.symbolPath, b.booth_id, b.constituency
            FROM candidate c
            LEFT JOIN booth b ON c.booth_id = b.booth_id
        """)
        rows = cursor.fetchall()

        print("\n=== Candidate Data ===")
        for row in rows:
            print(f"ID: {row[0]}, Name: {row[1]}, DOB: {row[2]}, Gender: {row[3]}, Phone: {row[4]}, "
                  f"Aadhar: {row[5]}, Constitution: {row[6]}, Contest Type: {row[7]}, "
                  f"Party Name: {row[8] or 'Independent'}, Image Path: {row[9]}, Symbol Path: {row[10]}, "
                  f"Booth ID: {row[11] or 'N/A'}, Booth Constituency: {row[12] or 'N/A'}")

    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")

    finally:
        cursor.close()


# ✅ Fetch Booth Data
def fetch_booth_data(connection):
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT booth_id, admin_id, constituency, modelPath
            FROM booth
        """)
        rows = cursor.fetchall()

        print("\n=== Booth Data ===")
        for row in rows:
            print(f"Booth ID: {row[0]}, Admin ID: {row[1]}, Constituency: {row[2]}, Model Path: {row[3] or 'N/A'}")

    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")

    finally:
        cursor.close()


# ✅ Main Function to Retrieve Data
def main():
    try:
        # ✅ Create Connection
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            print("Connected to the database")

            # ✅ Fetch Data
            fetch_voter_data(connection)
            fetch_candidate_data(connection)
            fetch_booth_data(connection)

    except mysql.connector.Error as e:
        print(f"Error: {e}")

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()
            print("Connection closed")

# ✅ Run the main function
if __name__ == "__main__":
    main()
