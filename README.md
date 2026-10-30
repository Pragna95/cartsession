# Online Shopping Cart and Session Management

React + FastAPI + MongoDB Atlas + DataStax Astra DB. Docker is not required.

- MongoDB Atlas stores the product catalogue and shopping cart documents.
- DataStax Astra DB (Cassandra-compatible) stores guest sessions and activity events.
- FastAPI connects to both cloud databases; React runs locally in your browser.

## 1. Create the cloud databases

### MongoDB Atlas
1. Create a project and a free cluster in MongoDB Atlas.
2. In **Database Access**, create a database user and save its username/password.
3. In **Network Access**, add your current IP address. For a temporary classroom demo only, you may use `0.0.0.0/0` if your IP changes often; this allows access from anywhere, so remove it after testing.
4. Open **Connect → Drivers → Python** and copy the connection string. Replace the username, password and cluster placeholders. URL-encode special characters in the password.

### DataStax Astra DB
1. Create an Astra DB Serverless database using the Cassandra API.
2. Create or select a keyspace in the Astra console. Copy its exact name; do not assume it is `default_keyspace`.
3. Generate an application token with database access.
4. Download the database's **Secure Connect Bundle** ZIP file for the region you selected.
5. Keep the token and ZIP private. Do not upload them to GitHub or share them in screenshots.

## 2. Configure backend credentials

1. Open the `backend` folder.
2. Copy `.env.example` and rename the copy to `.env`.
3. Fill in `MONGO_URI`, `ASTRA_TOKEN`, and the exact `ASTRA_KEYSPACE` from your Astra console.
4. Put the Secure Connect Bundle ZIP inside the `backend` folder and set `ASTRA_SECURE_CONNECT_BUNDLE=./your-actual-bundle-name.zip`.
5. Do not commit `.env` or the Secure Connect Bundle to Git.

The application creates its two tables inside the existing Astra keyspace. Astra keyspaces are created in the Astra console; this app does not issue `CREATE KEYSPACE`.

## 3. Run the backend on Windows (no Docker)

Open Command Prompt in the `backend` folder:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

A successful startup prints `Connected to MongoDB Atlas and DataStax Astra DB.`

Test the API at `http://127.0.0.1:8000/api/health` and open API documentation at `http://127.0.0.1:8000/docs`.

## 4. Run the React frontend

Open a second Command Prompt in the `frontend` folder:

```cmd
npm install
npm run dev
```

Open `http://localhost:5173`.

## Notes

- You need an internet connection while using the cloud databases.
- Never paste database passwords, application tokens, or Secure Connect Bundle files into chat or public repositories.
- This is a learning/demo project. It uses guest sessions and does not implement real authentication or payment processing.
