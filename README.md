# AI Medi Backend

<div align="center">

![AI Medi Backend](https://img.shields.io/badge/AI%20Medi-Backend%20API-green?style=for-the-badge)

</div>

A Flask-based RESTful API backend for managing patient records, medical sessions, and doctor accounts. This application uses Firebase Authentication and Firestore for data storage.

## ✨ Features

- 🔐 **JWT-based authentication** for doctors
- 👥 **Patient management** (CRUD operations)
- 📝 **Session notes and medical records**
- 🔒 **Secure Firebase integration**

## 🚀 Local Development Setup

### Prerequisites

- Python 3.8+ installed
- Firebase account and project
- Git

### Step 1: Clone the Repository

```bash
git clone https://github.com/karthiksathishjeemain/AI_medi_backend.git
cd AI_medi_backend
```

### Step 2: Set Up Firebase

1. Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Create a Firestore database in the project
3. Generate a new private key for service account:
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Save the downloaded file as `serviceAccountKey.json` in the project root

### Step 3: Create Environment Variables

Create a `.env` file in the project root:

```
SECRET_KEY=your_secret_key_here
# For local development, the app will use serviceAccountKey.json
# For production, set this:
# FIREBASE_CREDENTIALS={"type":"service_account",...} 
```

### Step 4: Set Up Virtual Environment

```bash
# On Windows
python -m venv newenv
.\newenv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 6: Run the Server

```bash
python app.py
```

The server will start on http://localhost:5000

## 📚 API Documentation

### Authentication

#### Register a Doctor

```bash
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@example.com",
    "password": "password123",
    "name": "Dr. Smith"
  }'
```

#### Login

```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@example.com",
    "password": "password123"
  }'
```

### Patient Management

#### Create Patient (Auth Required)

```bash
curl -X POST http://localhost:5000/api/patients \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "John Doe",
    "age": 45,
    "gender": "male",
    "notes": "Initial consultation"
  }'
```

#### Get All Patients (Auth Required)

```bash
curl -X GET http://localhost:5000/api/patients \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Specific Patient (Auth Required)

```bash
curl -X GET http://localhost:5000/api/patients/PATIENT_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Session Notes Management

#### Save Session Note

```bash
curl -X POST http://localhost:5000/api/patients/PATIENT_ID/session-note \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "note": "Patient reported improvement in symptoms after medication."
  }'
```

#### Update Session Note

```bash
curl -X PUT http://localhost:5000/api/session-notes/SESSION_ID \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "note": "Updated clinical observations and treatment plan."
  }'
```

#### Delete Session Note

```bash
curl -X DELETE http://localhost:5000/api/session-notes/SESSION_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Patient's Session Notes

```bash
curl -X GET http://localhost:5000/api/patients/PATIENT_ID/session-notes \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Specific Session Note

```bash
curl -X GET http://localhost:5000/api/session-notes/SESSION_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🧪 Testing with Postman

- Import the Postman collection
- Set up environment variables:
  - `baseUrl`: http://localhost:5000
  - `authToken`: (populated after login)

## 🚢 Deployment

### Deploying to Vercel

1. Install Vercel CLI: 
   ```bash
   npm i -g vercel
   ```

2. Add `vercel.json` file:
   ```json
   {
     "version": 2,
     "builds": [
       {
         "src": "app.py",
         "use": "@vercel/python"
       }
     ],
     "routes": [
       {
         "src": "/(.*)",
         "dest": "app.py"
       }
     ]
   }
   ```

3. Set up environment variables in Vercel dashboard:
   - `SECRET_KEY`: Your secret key
   - `FIREBASE_CREDENTIALS`: Contents of your serviceAccountKey.json

4. Deploy with: 
   ```bash
   vercel --prod
   ```

## 🔒 Security Notes

- Never commit your `serviceAccountKey.json` to version control
- Set proper environment variables in production
- Use HTTPS in production environments
- All endpoints are protected with JWT authentication
- Access controls ensure doctors can only access their own patients' data

## 🛠️ Technical Implementation

- Flask framework with RESTful API design
- Firebase Authentication for secure user management
- Firestore for scalable and flexible document storage
- JWT-based authentication for stateless API interactions
- Role-based access control for data protection

## 📄 License

[MIT](LICENSE)

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request