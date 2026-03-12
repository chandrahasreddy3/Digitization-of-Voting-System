import mysql.connector

# Database credentials
db_config = {
    'host': "localhost",
    'user': "root",
    'password': "Vishnu@MySQL#25",
    'database': 'VotingSystem'
}

# ✅ Create Tables
def create_tables():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        # ✅ Drop existing tables (if needed)
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

        # Drop tables in the right order
        cursor.execute("DROP TABLE IF EXISTS voter;")
        cursor.execute("DROP TABLE IF EXISTS candidate;")
        cursor.execute("DROP TABLE IF EXISTS constituency;")

        # ✅ Create Booth Table
        cursor.execute("""
            CREATE TABLE constituency (
                constituency_id VARCHAR(50) PRIMARY KEY,
                admin_id VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                constituency_name VARCHAR(100) NOT NULL,
                verified CHAR(1),
                modelPath VARCHAR(100) NULL,
                training_progress VARCHAR(100) NULL DEFAULT 'Not Started'
            );
        """)

        # ✅ Create Voter Table with constituency_id as a Foreign Key
        cursor.execute("""
            CREATE TABLE voter (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                gender ENUM('Male', 'Female', 'Other') NOT NULL,
                dob DATE NOT NULL,
                phone VARCHAR(15),
                aadhar VARCHAR(20) UNIQUE NOT NULL,
                voterId VARCHAR(20) UNIQUE NOT NULL,
                constituency_name VARCHAR(50),
                imagePath VARCHAR(100) NOT NULL,
                constituency_id VARCHAR(50),
                vote CHAR(1),
                FOREIGN KEY (constituency_id) REFERENCES constituency(constituency_id) 
                ON DELETE CASCADE 
                ON UPDATE CASCADE
            );
        """)

        cursor.execute("""
            CREATE TABLE candidate (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                gender ENUM('Male', 'Female', 'Other') NOT NULL,
                dob DATE NOT NULL,
                phone VARCHAR(15),
                aadhar VARCHAR(20) UNIQUE NOT NULL,
                constituency_name VARCHAR(50),
                contestType VARCHAR(50),
                partyName VARCHAR(50),
                imagePath VARCHAR(100) NOT NULL,
                symbolPath VARCHAR(100) NOT NULL,
                constituency_id VARCHAR(50),
                votes CHAR(1),
                FOREIGN KEY (constituency_id) REFERENCES constituency(constituency_id) 
                ON DELETE CASCADE 
                ON UPDATE CASCADE
            );
        """)

        connection.commit()
        print("Tables created successfully!")

    except mysql.connector.Error as e:
        print(f"Database error: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

# ✅ Register Booth with Manual Booth ID
def register_constituency(constituency_id, admin_id, password, constituency_name, model_path=None):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO constituency (constituency_id, admin_id, password, constituency_name, verified)
            VALUES (%s, %s, %s, %s, %s)
        """, (constituency_id, admin_id, password, constituency_name, model_path))

        connection.commit()
        print(f"✅ Constituency '{constituency_id}' registered successfully!")

    except mysql.connector.IntegrityError:
        print(f"❌ Error: Constituency with ID '{constituency_id}' already exists!")

    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()
            print("Connection closed")


# ✅ Register Voter with Linked Booth ID (if applicable)
def register_voter(name, dob, gender, phone, aadhar_number, voter_id, image_path, constituency_name, constituency_id=None):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO voter (name, gender, dob, phone, aadhar, voterId, constituency_name, imagePath, constituency_id, vote)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, gender, dob, phone, aadhar_number, voter_id, constituency_name, image_path, constituency_id, "N"))

        connection.commit()
        print(f"✅ Voter '{name}' registered successfully!")

    except mysql.connector.IntegrityError:
        print(f"❌ Error: Voter with Aadhar '{aadhar_number}' or Voter ID '{voter_id}' already exists!")

    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()
            print("Connection closed")


# ✅ Register Candidate with Linked Booth ID (if applicable)
def register_candidate(name, dob, gender, phone, aadhar, constituency_name, contestType, image_path, symbol_path, party_name=None, constituency_id=None):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO candidate (name, gender, dob, phone, aadhar, constituency_name, contestType, partyName, imagePath, symbolPath, constituency_id, votes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, gender, dob, phone, aadhar, constituency_name, contestType, party_name, image_path, symbol_path, constituency_id,"0"))

        connection.commit()
        print(f"✅ Candidate '{name}' registered successfully!")

    except mysql.connector.IntegrityError:
        print(f"❌ Error: Candidate with Aadhar '{aadhar}' already exists!")

    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()
            print("Connection closed")



def checkFor(table, aadhar, constituency_name):
    """Check if a voter exists by aadhar number in a specific constituency."""
    if table not in ['voter', 'candidate']:
        print("❌ Invalid table name!")
        return False

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = f"SELECT 1 FROM {table} WHERE aadhar = %s AND constituency_name = %s LIMIT 1"
        cursor.execute(query, (aadhar, constituency_name))
        result = cursor.fetchone()
        return result is not None  

    except mysql.connector.Error as err:
        print(f"❌ Database Error: {err}")
        return False  

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()






# ✅ Main Function
def main():

    # ✅ Create Tables
    create_tables()

    # ✅ Register Booths
    register_constituency("C01", "admin01", "pass1", "Yelahanka", "N")
    register_constituency("C02", "admin02", "pass2", "Yeshwanthpura", "N")


    # ✅ Register Voters Linked to Booths
    # register_voter(connection, "John Doe", "1990-05-15", "Male", "9876543210", "123456789012", "VOTER123", "B001")
    # register_voter(connection, "Jane Doe", "1992-07-20", "Female", "9876543211", "123456789013", "VOTER124", "B002")

# ✅ Run the main function
if __name__ == "__main__":
    main()
