from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import base64
import os
import shutil
import threading
import mysql.connector
from FlaskDatabase1 import register_voter, register_candidate, checkFor
from FaceModel import augment, FaceRecognition, FaceVerification

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

db_config = {
    'host': "localhost",
    'user': "root",
    'password': "Vishnu@MySQL#25",
    'database': 'VotingSystem'
}

CID = {
    "Yelahanka": "C01",
    "Yeshwanthpura": "C02"
}

progressMap = {
    "Not Started": -1,
    "Training Started": 0,
    "Augmenting images...": 20,
    "Loading dataset...": 40,
    "Converting faces to embeddings...": 60,
    "Training model...": 80,
    "Training completed!": 100
}

app = Flask(__name__)
app.secret_key = "secret123"

@app.route('/')
def Home():
    return render_template('index.html')

@app.route('/RegisterPage')
def Register():
    return render_template('RegisterPage.html')

@app.route('/RegisterVoter')
def RegisterVoter():
    return render_template('VoterRegister.html')

@app.route('/RegisterCandidate')
def RegisterCandidate():
    return render_template('CandidateRegister.html')

@app.route('/Login')
def Login():
    return render_template('LoginPage.html')


@app.route('/AdminLogin', methods=['GET', 'POST'])
def AdminLogin():
    if request.method == 'POST':
        admin_id = request.form['admin_id']
        password = request.form['password']
        
        try:
            # Connect to the database
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)

            # Query the constituency table
            cursor.execute("SELECT * FROM constituency WHERE admin_id = %s AND password = %s", (admin_id, password))
            admin = cursor.fetchone()
            
            if admin:
                if admin['admin_id'] == 'admin00':
                    return redirect(url_for('MainAdmin'))  # Redirect to the main admin page
                session['admin_id'] = admin['admin_id']
                return redirect(url_for('AdminVerify'))  # Redirect to the verification page
            else:
                return render_template('AdminLogin.html', error='❌ Invalid Admin ID or Password!')

        except mysql.connector.Error as e:
            return render_template('AdminLogin.html', error=f"❌ Database error: {e}")

        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'connection' in locals() and connection.is_connected():
                connection.close()

    return render_template('AdminLogin.html')

@app.route('/MainAdmin', methods=['GET', 'POST'])
def MainAdmin():
    if 'admin_id' not in session:
        return redirect(url_for('AdminLogin'))
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT c.constituency_id AS constituency_id, c.constituency_name AS constituency_name, c.training_progress AS training_progress, COUNT(DISTINCT v.id) AS voter_count, COUNT(DISTINCT ca.id) AS candidate_count " \
        "FROM constituency c LEFT JOIN voter v ON c.constituency_id = v.constituency_id LEFT JOIN candidate ca ON c.constituency_id = ca.constituency_id " \
        "GROUP BY c.constituency_id, c.constituency_name")
        constituencies = cursor.fetchall()
        cursor.execute("SELECT verified FROM constituency where constituency_id = 'C00'")
        verified = cursor.fetchone()
        print("Admin is verified as:", verified['verified'])
    except mysql.connector.Error as e:
        print(f"Database error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()
    return render_template('MainAdmin.html', constituencies=constituencies[1:], verified=verified['verified'])

from flask import redirect, url_for

@app.route('/AdminVotingCommand/<command>')
def AdminVotingCommand(command):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        if command == 'start':
            cursor.execute("UPDATE voter SET vote = 'N'")
            cursor.execute("UPDATE candidate SET votes = 0")
            cursor.execute("UPDATE constituency SET verified = 'Y' WHERE constituency_id = %s", ('C00',))
            connection.commit()
            print("Voting started successfully!")
        elif command == 'stop':
            cursor.execute("UPDATE constituency SET verified = 'N' WHERE constituency_id = %s", ('C00',))
            connection.commit()
            print("Voting stopped successfully!")
        
        # After update, redirect to the main admin page
        return redirect(url_for('MainAdmin'))

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return f"Database error: {e}", 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()


@app.route('/AdminVerify', methods=['GET', 'POST'])
def AdminVerify():
    if 'admin_id' not in session:
        return redirect(url_for('AdminLogin'))

    voters = []
    candidates = []

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT constituency_id, constituency_name FROM constituency WHERE admin_id = %s", (session['admin_id'],))
        constituency = cursor.fetchone()

        if constituency:
            constituency_id = constituency['constituency_id']
            constituency = constituency['constituency_name']
            print(constituency," Constituency's Admin as logged in")

            cursor.execute("""
                SELECT name, gender, dob, phone, aadhar, voterId, constituency_name, imagePath
                FROM voter 
                WHERE constituency_id = %s
            """, (constituency_id,))
            voters = cursor.fetchall()
            cursor.execute("""
                SELECT name, gender, dob, phone, aadhar, constituency_name, contestType, partyName, imagePath, symbolPath 
                FROM candidate 
                WHERE constituency_id = %s
            """, (constituency_id,))
            candidates = cursor.fetchall()

        else:
            return "constituency not found for the logged-in admin.", 404

    except mysql.connector.Error as e:
        print(f"Database error: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

    return render_template('AdminVerify.html', constituency_name = constituency, voters=voters, candidates=candidates)


@app.route('/deny/<entity>/<entity_id>', methods=['POST'])
def deny(entity, entity_id):
    valid_entities = ['voter', 'candidate']  # Whitelist valid table names
    if entity not in valid_entities:
        print(f"Invalid entity: {entity}")
        return redirect(url_for('AdminVerify'))
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        query = f'SELECT imagePath FROM {entity} WHERE aadhar = %s'
        cursor.execute(query, (entity_id,))
        candidate = cursor.fetchone()
        if candidate:
            image_path = candidate['imagePath']
            candidate_folder = os.path.dirname(image_path)
            if os.path.exists(candidate_folder):
                shutil.rmtree(candidate_folder)
                print(f"Folder at {candidate_folder} deleted.")

            cursor.execute(f"DELETE FROM {entity} WHERE aadhar = %s", (entity_id,))
            connection.commit()
            print(f"{entity.capitalize()} with aadhar '{entity_id}' denied and removed from the '{entity}' database!")
        else:
            print(f"{entity.capitalize()} with aadhar '{entity_id}' not found in the '{entity}' database.")

    except mysql.connector.Error as e:
        print(f"Database error while denying candidate {entity_id}: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

    return redirect(url_for('AdminVerify'))


@app.route('/checkProgress/<constituency_name>', methods=['GET'])
def checkProgress(constituency_name):
    connection = None
    cursor = None

    try:
        # Connect to the database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        # Fetch training progress
        cursor.execute("SELECT training_progress, modelPath FROM constituency WHERE constituency_name = %s", (constituency_name,))
        result = cursor.fetchone()

        if result:
            model_path = 1 if result['modelPath'] is not None else 0
            progress = progressMap.get(result['training_progress'], 0)  # Avoid KeyError with .get()
            print(f"{result['training_progress']} Progress: {progress}% || ModelPresence: {model_path}")
            return jsonify({"progress": progress, "model_path": model_path}), 200
        else:
            return jsonify({"error": "Constituency not found"}), 404

    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Close cursor and connection
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def update_progress(cursor, constituency_name, status):
    """Update the training progress in the database."""
    print(f"Status of {constituency_name} Constituency model training:", status)
    cursor.execute("""
        UPDATE constituency SET training_progress = %s WHERE constituency_name = %s
    """, (status, constituency_name))


def train_model_async(constituency_name):
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        print(f"Model Training started for {constituency_name} Constituency...")
        cursor.execute("SELECT verified FROM constituency WHERE constituency_name = %s", (constituency_name,))
        constituency = cursor.fetchone()
        print(constituency_name, " Constituency is verified as: ", constituency['verified'])

        if constituency and constituency['verified'] == 'Y':
            update_progress(cursor, constituency_name, "Model is already trained!")
            connection.commit()
            return

        folder_path = os.path.join('static', constituency_name, 'Voters')
        update_progress(cursor, constituency_name, "Augmenting images...")
        connection.commit()
        augment(folder_path)

        fr = FaceRecognition(folder_path, constituency_name)

        update_progress(cursor, constituency_name, "Loading dataset...")
        connection.commit()
        fr.load_dataset()

        update_progress(cursor, constituency_name, "Converting faces to embeddings...")
        connection.commit()
        fr.convert_to_embeddings()

        update_progress(cursor, constituency_name, "Training model...")
        connection.commit()
        model_path = fr.train_model()
        print("Model trained and saved at:", model_path)
        update_progress(cursor, constituency_name, "Training completed!")
        cursor.execute("""
            UPDATE constituency SET verified = 'Y', modelPath = %s, training_progress = 'Training completed!'
            WHERE constituency_name = %s
        """, (model_path, constituency_name,))
        connection.commit()

    except mysql.connector.Error as e:
        update_progress(cursor, constituency_name, f"Database error: {e}")
        connection.commit()

    except Exception as e:
        update_progress(cursor, constituency_name, f"Training failed: {e}")
        connection.commit()

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/ConfirmTraining/<constituency_name>')
def ConfirmTraining(constituency_name):
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        print(f"Confirming training for {constituency_name} Constituency...")
        cursor.execute("SELECT verified, training_progress FROM constituency WHERE constituency_name = %s", (constituency_name,))
        constituency = cursor.fetchone()

        if not constituency:
            return "Constituency not found.", 404

        if constituency["verified"] == "Y":
            return "Model is already trained!", 400
        elif "Training" in constituency["training_progress"]:
            return "Training is already in progress...", 200
        training_thread = threading.Thread(target=train_model_async, args=(constituency_name,))
        training_thread.start()
        print(f"Training started for {constituency_name} Constituency...")
        update_progress(cursor, constituency_name, "Starting training...")
        connection.commit()
        return "Training started!", 200

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return f"Database error: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/deleteModel/<constituency_name>', methods=['DELETE'])
def deleteModel(constituency_name):
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT modelPath FROM constituency WHERE constituency_name = %s", (constituency_name,))
        result = cursor.fetchone()

        if not result or not result['modelPath']:
            return jsonify({"error": "Model not found for this constituency."}), 404

        model_path = result['modelPath']
        voters_folder = os.path.join("static", constituency_name, "Voters")  # Path to Voters folder
        if os.path.exists(model_path):
            shutil.rmtree(model_path)
            print(f"Deleted model folder: {model_path}")
        if os.path.exists(voters_folder):
            for voter_name in os.listdir(voters_folder):  # Iterate through voter folders
                voter_path = os.path.join(voters_folder, voter_name)
                if os.path.isdir(voter_path):  # Ensure it's a folder
                    augmented_path = os.path.join(voter_path, "Augmented")
                    # Delete Augmented folder if it exists
                    if os.path.exists(augmented_path):
                        shutil.rmtree(augmented_path)
                        print(f"Deleted Augmented folder: {augmented_path}")
        cursor.execute("""
            UPDATE constituency 
            SET modelPath = NULL, verified = 'N', training_progress = 'Not Started' 
            WHERE constituency_name = %s
        """, (constituency_name,))
        connection.commit()

        return jsonify({"message": "Model and Voters Augmented images deleted successfully!"}), 200

    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route('/VoterLogin')
def VoterLogin():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT verified FROM constituency where constituency_id = 'C00'")
        verified = cursor.fetchone()
        print("Admin is verified as:", verified['verified'])
    except mysql.connector.Error as e:
        print(f"Database error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()
    return render_template('VoterLogin.html', verified=verified['verified'])

@app.route('/getConstitutions', methods=['GET'])
def getConstitutions():
    NAMES = list(CID.keys())
    return jsonify(NAMES)


@app.route('/getVoterInfo/<voter_id>', methods=['GET'])
def get_voter_info(voter_id):
    connection = None
    cursor = None

    try:
        # Connect to the database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        # Fetch training progress
        cursor.execute("SELECT name, aadhar, constituency_name, vote FROM voter WHERE voterId = %s", (voter_id,))
        result = cursor.fetchone()

        if result:
            print(f"Voter {result['name']} with voterId {voter_id} and AadharId {result['aadhar']} found in {result['constituency_name']} Constituency.")
            return jsonify({"status": "success", "VoterName": result['name'], "Aadhar": result['aadhar'], "Constituency": result['constituency_name'], "Vote": result['vote']}), 200
        else:
            return jsonify({"status": "error", "message": "Voter not found!"}), 404

    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Close cursor and connection
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route('/getCandidates/<constituency>', methods=['GET'])
def get_candidates(constituency):
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT name, aadhar, imagePath, symbolPath, contestType ,partyName FROM candidate WHERE constituency_name = %s", (constituency,))
        candidates = cursor.fetchall()
        if candidates:
            return render_template('Vote.html', constituency=constituency, candidates=candidates)
    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

face_verifier = None

@app.route('/load_model', methods=['POST'])
def load_model():
    global face_verifier

    data = request.json
    constituency = data.get('constituency')
    VoterName = data.get('voterName')
    VoterId = data.get('voterId')

    connection = None
    cursor = None

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT modelPath FROM constituency WHERE constituency_name = %s", (constituency,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"status": "error", "message": "Constituency not found!"}), 404
        if result['modelPath'] == "N":
            return jsonify({"status": "error", "message": "Not Verified By the Admin!"}), 404

        # Initialize FaceVerification object
        face_verifier = FaceVerification(VoterId, VoterName, constituency, cursor)
        print(f"Model loaded for constituency ID: {constituency}")
        return jsonify({"status": "success", "message": "Model loaded successfully!"}), 200

    except ValueError as ve:
        return jsonify({"status": "error", "message": "Not Verified By the Admin!"}), 404

    except Exception as e:
        import traceback
        print(f"Error loading model: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Failed to load the model"}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/process_frame', methods=['POST'])
def process_frame():
    global face_verifier

    if not face_verifier:
        return jsonify({"status": "error", "message": "Model not loaded"}), 400

    data = request.json
    image_data = data.get('image')

    if not image_data:
        return jsonify({"status": "error", "message": "Image data is required"}), 400

    try:
        result = face_verifier.process_frame(image_data)
        result_data = result.get_json()

        if result_data.get('status') == 'success':
            if result_data.get('match'):
                return jsonify({"status": "success", "message": "Face verified successfully", "match": True}), 200
            else:
                return jsonify({"status": "success", "message": "Face does not match with the registered voter", "match": False}), 200
        else:
            return jsonify(result_data), 400

    except Exception as e:
        print(f"Error processing frame: {e}")
        return jsonify({"status": "error", "message": "Failed to process frame"}), 500


@app.route('/VotePage')
def VotePage():
    constituency = request.args.get('constituency')
    aadhar = request.args.get('aadhar')
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT name, imagePath, aadhar, symbolPath, contestType ,partyName FROM candidate WHERE constituency_name = %s", (constituency,))
    candidates = cursor.fetchall()
    return render_template('Vote.html', constituency=constituency, Aadhar=aadhar, candidates=candidates)


@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    try:
        data = request.get_json()
        voter_aadhar = data.get('VoterAadhar')
        candidate_aadhar = data.get('CandidateAadhar')
        constituency = data.get('constituency')

        print("Voter with Aadhar:", voter_aadhar, "is casting vote in ", constituency, " constituency for candidate with aadhar:", candidate_aadhar)

        if not voter_aadhar:
            return jsonify({"status": "error", "message": "Voter Aadhar requirements are not satisfied by the webpage response!"}), 400
        if not candidate_aadhar:
            return jsonify({"status": "error", "message": "Candidate Aadhar requirements are not satisfied by the webpage response!"}), 400
        if not constituency:
            return jsonify({"status": "error", "message": "Constituency requirements are not satisfied by the webpage response!"}), 400
        
        
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)

        # Increment vote count and Mark the voter as voted if it's not NOTA
        if candidate_aadhar != 'NOTA':
            print("Casting vote for candidate:", candidate_aadhar)
            cursor.execute("""
                UPDATE candidate SET votes = votes + 1 
                WHERE aadhar = %s AND constituency_name = %s
            """, (candidate_aadhar, constituency))

            print("Marking voter as voted:", voter_aadhar)
            cursor.execute("""
                UPDATE voter SET vote = 'Y' 
                WHERE aadhar = %s AND constituency_name = %s
            """, (voter_aadhar, constituency))

        connection.commit()

        # Fetch candidate details
        if candidate_aadhar != 'NOTA':
            print("Fetching candidate details for:", candidate_aadhar)
            cursor.execute("""
                SELECT name, constituency_name, imagePath, symbolPath, contestType, partyName 
                FROM candidate WHERE aadhar = %s
            """, (candidate_aadhar,))
            result = cursor.fetchone()
            if result:
                print("Candidate details fetched successfully:", result)
                redirect_url = url_for('vote_preview', 
                                       Constituency = result['constituency_name'],
                                       CandidateName = result['name'],
                                       Image = result['imagePath'],
                                       Symbol = result['symbolPath'],
                                       ContestType = result['contestType'],
                                       PartyName = result['partyName'])
        else:
            print("Casting vote for NOTA")
            redirect_url = url_for('vote_preview', Constituency = constituency, CandidateName = 'NOTA')

        return jsonify({"status": "success", "redirect_url": redirect_url})

    except Exception as e:
        print("Error casting vote:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/vote_preview')
def vote_preview():
    Constituency = request.args.get('Constituency')
    CandidateName = request.args.get('CandidateName')
    Image = request.args.get('Image', default='../static/Nota.png')
    Symbol = request.args.get('Symbol')
    ContestType = request.args.get('ContestType')
    PartyName = request.args.get('PartyName')

    return render_template('VotePreview.html',
                           Constituency=Constituency,
                           CandidateName=CandidateName,
                           Image=Image,
                           Symbol=Symbol,
                           ContestType=ContestType,
                           PartyName=PartyName)


@app.route('/view_voting', methods=['POST'])
def view_voting():
    try:
        data = request.get_json()
        constituency_id = data.get('constituency_id')

        # You could also store the data in session, or pass via URL
        return jsonify({
            "status": "success",
            "redirect_url": url_for('view_voting_page', constituency_id=constituency_id)
        })

    except Exception as e:
        print("Error viewing voting:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/view_voting_page/<constituency_id>')
def view_voting_page(constituency_id):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT name, aadhar, imagePath, symbolPath, contestType ,partyName, votes FROM candidate
        WHERE constituency_id = %s
        ORDER BY votes DESC
    """, (constituency_id,))
    candidates = cursor.fetchall()
    print("Candidates imagePath:", candidates[0]['imagePath'])
    print("Candidates symbolPath:", candidates[0]['symbolPath'])

    cursor.execute("""
        SELECT constituency_name FROM constituency WHERE constituency_id = %s
    """, (constituency_id,))
    constituency = cursor.fetchone()

    return render_template('ViewVoting.html',
                           constituency=constituency['constituency_name'],
                           candidates=candidates)


@app.route('/submitVoterRegistration', methods=['POST'])
def submit_voter_registration():
    data = request.json
    voter_id = data['VoterId']
    constituency = data['Constitution']
    aadhar = data['Aadhar']

    if checkFor("voter", aadhar, constituency):
        return jsonify({"message": "Voter already registered"}), 400

    BASE_DIR = 'static'

    user_dir = os.path.join(BASE_DIR, constituency, "Voters", aadhar)
    os.makedirs(user_dir, exist_ok=True)
    image_path = os.path.join(user_dir, f"{aadhar}.png")

    with open(image_path, "wb") as f:
        f.write(base64.b64decode(data['Image'].split(",")[1]))

    image_path = f"static/{constituency}/Voters/{aadhar}/{aadhar}.png"

    register_voter(
        data['Name'], data['Dob'], data['Gender'], data['Phone'],
        data['Aadhar'], voter_id, image_path, constituency, CID[constituency]
    )

    return jsonify({"message": "Voter Registration successful"}), 200

@app.route('/submitCandidateRegistration', methods=['POST'])
def submit_candidate_registration():
    data = request.json
    aadhar = data['Aadhar']
    constituency = data['Constitution']

    if checkFor("candidate", aadhar, constituency):
        return jsonify({"message": "Candidate already registered"}), 400

    BASE_DIR = 'static'
    user_dir = os.path.join(BASE_DIR, constituency, "Candidates", aadhar)
    os.makedirs(user_dir, exist_ok=True)
    image_path = os.path.join(user_dir, f"C{aadhar}.png")
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(data['Image'].split(",")[1]))
    image_path = f"static/{constituency}/Candidates/{aadhar}/C{aadhar}.png"

    symbol_path = os.path.join(user_dir, f"S{aadhar}.png")
    with open(symbol_path, "wb") as f:
        f.write(base64.b64decode(data['Symbol'].split(",")[1]))
    symbol_path = f"static/{constituency}/Candidates/{aadhar}/S{aadhar}.png"

    register_candidate(
        data['Name'], data['Dob'], data['Gender'], data['Phone'],
        aadhar, constituency, data['ContestType'], image_path, symbol_path, data.get('PartyName'), CID[constituency]
    )

    return jsonify({"message": "Candidate Registration successful"}), 200

@app.route('/dashboard')
def dashboard():
    if "user" in session:
        return render_template("dashboard.html", username=session["user"])
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


if __name__ == '__main__':
   app.run(debug=False)
