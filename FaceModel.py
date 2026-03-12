import os
import cv2
import imgaug.augmenters as iaa
import numpy as np
import pickle
import base64
from mtcnn.mtcnn import MTCNN
from keras_facenet import FaceNet
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score
import pickle
from flask import jsonify, request

def augment(folder):
    # Create an augmentation sequence
    augmenters = iaa.Sequential([
        iaa.Fliplr(0.5),  # Flip horizontally with 50% probability
        iaa.Affine(rotate=(-30, 30)),  # Rotate between -30 to 30 degrees
        iaa.Multiply((0.8, 1.2)),  # Change brightness
        iaa.GaussianBlur(sigma=(0.0, 1.0)),  # Apply slight blur
        iaa.AdditiveGaussianNoise(scale=(0, 0.05*255)),  # Add noise
        iaa.Crop(percent=(0, 0.2)),  # Random crop up to 20%
    ])

    def get_subdirectories(base_dir):
        subdirectories = []
        for root, dirs, _ in os.walk(base_dir):
            for dir in dirs:
                subdirectories.append(os.path.join(root, dir))  # Append full path to subdirectories
        return subdirectories

    subfolders = get_subdirectories(folder)

    for subfolder in subfolders:
        print(f"Processing subfolder: {subfolder}")
        
        # Create "Augmented" folder if not exists
        augmented_folder = os.path.join(subfolder, "Augmented")
        os.makedirs(augmented_folder, exist_ok=True)

        for file in os.listdir(subfolder):
            if file.lower().endswith('.png'):
                image_path = os.path.join(subfolder, file)
                image = cv2.imread(image_path)
                if image is None:
                    print(f"Failed to read image: {image_path}")
                    continue
                
                # Generate 20 augmented images per original image
                for i in range(20):
                    augmented_image = augmenters(image=image)
                    base_filename, ext = os.path.splitext(file)
                    augmented_image_name = f"{base_filename}_{i+1}{ext}"
                    output_path = os.path.join(augmented_folder, augmented_image_name)
                    cv2.imwrite(output_path, augmented_image)

                print(f"20 unique augmented images for {file} have been saved successfully in {augmented_folder}")

    print("Augmentation completed for all images in subfolders.")




import cv2 as cv
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

class FaceRecognition:
    def __init__(self, dataset_dir, constitution):
        self.dataset_dir = dataset_dir
        self.constitution = constitution
        self.target_size = (160, 160)
        self.detector = MTCNN()
        self.embedder = FaceNet()
        self.model = None
        self.encoder = LabelEncoder()
        self.X, self.Y = [], []

    def extract_face(self, filename):
        """Extracts face from an image using MTCNN."""
        img = cv.imread(filename)
        img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        detections = self.detector.detect_faces(img)
        if detections:
            x, y, w, h = detections[0]['box']
            x, y = abs(x), abs(y)
            face = img[y:y+h, x:x+w]
            face_arr = cv.resize(face, self.target_size)
            return face_arr
        return None

    def load_dataset(self):
        """Loads dataset images, extracts faces, and assigns labels."""
        voters_path = os.path.join(self.dataset_dir)
        
        for sub_dir in os.listdir(voters_path):
            voter_path = os.path.join(voters_path, sub_dir, "Augmented")
            
            # Skip if Augmented folder doesn't exist
            if not os.path.isdir(voter_path):
                print(f"No Augmented folder found for {sub_dir}, skipping...")
                continue
            
            faces = []
            for img_name in os.listdir(voter_path):
                try:
                    img_path = os.path.join(voter_path, img_name)
                    face = self.extract_face(img_path)
                    if face is not None:
                        faces.append(face)
                except Exception as e:
                    print(f"Error processing {img_name}: {e}")
            
            if faces:
                labels = [sub_dir] * len(faces)
                self.X.extend(faces)
                self.Y.extend(labels)
                print(f"Loaded {len(faces)} images for class '{sub_dir}'.")

        self.X = np.asarray(self.X)
        self.Y = np.asarray(self.Y)
        print(f"Total faces loaded: {len(self.X)} across {len(set(self.Y))} voters.")


        self.X = np.asarray(self.X)
        self.Y = np.asarray(self.Y)

    def get_embedding(self, face_img):
        """Converts a face image into a 512D embedding using FaceNet."""
        face_img = face_img.astype('float32')
        face_img = np.expand_dims(face_img, axis=0)
        return self.embedder.embeddings(face_img)[0]

    def convert_to_embeddings(self):
        """Converts all extracted faces into embeddings."""
        # Create the constitution model directory if it does not exist
        self.model_dir = os.path.join(self.dataset_dir, f"{self.constitution}Model")
        os.makedirs(self.model_dir, exist_ok=True)
        self.X = np.array([self.get_embedding(face) for face in self.X])
        np.savez_compressed(os.path.join(self.model_dir, 'faces_embeddings.npz'), self.X, self.Y)

    def train_model(self):
        """Encodes labels, splits data, trains an SVM model, and evaluates it."""
        self.encoder.fit(self.Y)
        self.Y = self.encoder.transform(self.Y)
        X_train, X_test, Y_train, Y_test = train_test_split(self.X, self.Y, shuffle=True, random_state=17)

        self.model = SVC(kernel='linear', probability=True)
        self.model.fit(X_train, Y_train)

        train_acc = accuracy_score(Y_train, self.model.predict(X_train))
        test_acc = accuracy_score(Y_test, self.model.predict(X_test))

        print(f"Training Accuracy: {train_acc:.4f}")
        print(f"Testing Accuracy: {test_acc:.4f}")

        with open(os.path.join(self.model_dir, 'model.pkl'), 'wb') as f:
            pickle.dump(self.model, f)

        return self.model_dir

    def load_trained_model(self):
        """Loads the trained SVM model and label encoder."""
        self.model_dir = os.path.join(self.dataset_dir, f"{self.constitution}Model")

        # Load model
        model_path = os.path.join(self.model_dir, 'model.pkl')
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        # Load label encoder from the embeddings file
        embeddings_path = os.path.join(self.model_dir, 'faces_embeddings.npz')
        data = np.load(embeddings_path)
        self.Y = data['arr_1']
        self.encoder.fit(self.Y)

        print("Model and encoder loaded successfully.")

    def predict(self, test_image_path):
        """Predicts the class of a new image."""
        if self.model is None:
            print("Model not loaded. Call 'load_trained_model()' first.")
            return

        img = cv.imread(test_image_path)
        img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
        detections = self.detector.detect_faces(img)
        if detections:
            x, y, w, h = detections[0]['box']
            x, y = abs(x), abs(y)
            face = img[y:y+h, x:x+w]
            face = cv.resize(face, self.target_size)

            # Generate embedding and make prediction
            embedding = self.get_embedding(face)
            y_pred = self.model.predict([embedding])
            predicted_label = self.encoder.inverse_transform(y_pred)
            print(f"Predicted Label: {predicted_label[0]}")
            return predicted_label[0]
        else:
            print("No face detected in the image.")
            return None




class FaceVerification:
    def __init__(self, VoterId, VoterName, constituency, cursor):
        self.VoterId = VoterId
        self.Aadhar = self._get_aadhar(cursor)
        self.VoterName = VoterName
        self.constituency = constituency
        self.model_folder = self._get_model_folder(cursor)
        self.facenet = FaceNet()
        self.haarcascade = cv.CascadeClassifier('haarcascade_frontalface_default.xml')
        self.recognized_face = None
        self.encoder = LabelEncoder()
        self.model = None
        self._load_model_data()

    def _get_aadhar(self,cursor):
        """Fetch Aadhar number from the database using VoterId."""
        cursor.execute("""
            SELECT aadhar FROM voter WHERE voterId = %s
        """, (self.VoterId,))
        result = cursor.fetchone()
        return result["aadhar"]

    def _get_model_folder(self,cursor):
        """Fetch model folder path from the database using constituency_id."""
        cursor.execute("""
            SELECT modelPath FROM constituency WHERE constituency_name = %s
        """, (self.constituency,))
        result = cursor.fetchone()

        if not result:
            raise ValueError("{self.constituency} Constituency not found.")
        return result["modelPath"]
    

    def _load_model_data(self):
        """Load embeddings and model from the model folder."""
        try:
            embeddings_path = f"{self.model_folder}/faces_embeddings.npz"
            model_path = f"{self.model_folder}/model.pkl"
            
            # Load embeddings
            faces_embeddings = np.load(embeddings_path)
            self.X, self.Y = faces_embeddings['arr_0'], faces_embeddings['arr_1']

            # Encode labels
            self.encoder.fit(self.Y)

            # Load saved model
            with open(model_path, 'rb') as model_file:
                self.model = pickle.load(model_file)

            print(f"Model and embeddings loaded successfully from {self.model_folder}")

        except Exception as e:
            print(f"Error loading model data: {e}")
            raise

    def process_frame(self, image_data):
        """Process a single frame for face recognition."""
        try:
            # Decode the base64 image data
            image = base64.b64decode(image_data.split(',')[1])
            np_arr = np.frombuffer(image, np.uint8)
            frame = cv.imdecode(np_arr, cv.IMREAD_COLOR)

            # Convert to RGB and grayscale for detection
            rgb_img = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            gray_img = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

            # Detect faces using Haarcascade
            faces = self.haarcascade.detectMultiScale(gray_img, 1.3, 5)

            for x, y, w, h in faces:
                img = rgb_img[y:y + h, x:x + w]
                img = cv.resize(img, (160, 160))
                img = np.expand_dims(img, axis=0)

                # Get embeddings and predict
                ypred = self.facenet.embeddings(img)
                face_name = self.model.predict(ypred)
                self.recognized_face = self.encoder.inverse_transform(face_name)[0]

                # Check if recognized face matches VoterName
                if self.recognized_face == self.Aadhar:
                    return jsonify({"message": f"Recognized face: {self.recognized_face}", "status": "success", "match": True})
                else:
                    return jsonify({"message": f"Face mismatch: Expected {self.VoterName}, but got {self.recognized_face}", "status": "success", "match": False})

            return jsonify({"message": "No face detected", "status": "error", "match": False})

        except Exception as e:
            print(f"Error during face recognition: {e}")
            self.recognized_face = None
            return jsonify({"message": "Face recognition failed", "status": "error", "match": False})
